"""PrintFlow: lo que las tiendas online toman de PrintFlow.

- En qué tiendas se vende cada artículo: las tiendas (Medusa) mandan su lista en
  cada sincronización y reciben en qué tiendas va cada artículo; se elige en
  PrintFlow y la tienda lo obedece. La primera vez la tienda manda lo que ya
  tenía, para no vaciarla.
- Tamaños: un artículo "producto con tamaños" agrupa otros artículos (cada uno
  un tamaño, con su SKU, precio y stock); en la tienda sale una sola ficha con
  selector de tamaño, con el nombre, descripción, foto, categoría y tiendas del
  producto con tamaños.
- Cajas: cada artículo puede llevar una caja (artículo de embalaje) cuyo coste
  se suma a su precio en la tienda.
- Envío a domicilio: su precio, igual para todas las tiendas.
- Personalización: qué elige el cliente en cada producto (un color, colores y
  una descripción, o pintarlo en la web).
- Colores: los filamentos con bobinas empezadas o llenas, con el nombre que se
  les da en la tienda; un color sin bobinas desaparece solo.

Rutas bajo /api/v1/items (se registran antes que las de FilaOps para que
/items/nebula/... no choque con /items/{item_id}).
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.v1.deps import get_current_staff_user
from app.db.session import get_db
from app.models.material import Color
from app.models.material_spool import MaterialSpool
from app.models.nebula_product import ProductShopOption, ProductShopStore, ShopColor, ShopSettings, ShopStore
from app.models.product import Product
from app.models.user import User

router = APIRouter()


def _product(db: Session, item_id: int) -> Product:
    product = db.query(Product).filter(Product.id == item_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    return product


class ShopStoreIn(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    domains: List[str] = []


class ShopStoresIn(BaseModel):
    stores: List[ShopStoreIn]
    # Lo que ya hay en las tiendas; solo se usa si aún no se ha elegido nada
    seed: Optional[Dict[int, List[str]]] = None


class ItemShopsIn(BaseModel):
    store_ids: List[str]


class ShopSizeIn(BaseModel):
    product_id: int
    size_label: str = Field(..., min_length=1, max_length=100)


class ShopSizesIn(BaseModel):
    sizes: List[ShopSizeIn]


class ShopBoxIn(BaseModel):
    box_id: Optional[int] = None


class ShopSettingsIn(BaseModel):
    home_shipping_price: Decimal = Field(..., ge=0, le=10000)


CUSTOMIZATIONS = ("none", "color", "describe", "paint")


class ShopCustomizationIn(BaseModel):
    customization: str = Field(..., pattern="^(none|color|describe|paint)$")


class ShopColorIn(BaseModel):
    shop_name: Optional[str] = Field(None, max_length=100)
    hidden: bool = False


def box_cost(box: Optional[Product]) -> Decimal:
    """Coste de una caja: el estándar si se costea así; si no, el medio, el último o el estándar."""
    if box is None:
        return Decimal("0")
    order = [box.average_cost, box.last_cost, box.standard_cost]
    if box.cost_method == "standard":
        order.insert(0, box.standard_cost)
    for value in order:
        if value is not None and value > 0:
            return Decimal(value).quantize(Decimal("0.01"))
    return Decimal("0")


def _settings(db: Session) -> ShopSettings:
    settings = db.get(ShopSettings, 1)
    if settings is None:
        settings = ShopSettings(id=1, home_shipping_price=Decimal("0"))
        db.add(settings)
        db.flush()
    return settings


def _option(db: Session, product_id: int) -> ProductShopOption:
    option = db.get(ProductShopOption, product_id)
    if option is None:
        option = ProductShopOption(product_id=product_id, position=0)
        db.add(option)
    return option


def _assignments(db: Session) -> Dict[int, List[str]]:
    result: Dict[int, List[str]] = {}
    for row in db.query(ProductShopStore).order_by(ProductShopStore.product_id, ProductShopStore.store_id):
        result.setdefault(row.product_id, []).append(row.store_id)
    return result


def shop_colors(db: Session, include_hidden: bool = False) -> List[dict]:
    """Un color por filamento (material + color) con bobinas activas que no estén vacías."""
    spools = (
        db.query(MaterialSpool)
        .options(
            joinedload(MaterialSpool.product).joinedload(Product.color),
            joinedload(MaterialSpool.product).joinedload(Product.material_type),
        )
        .filter(MaterialSpool.status == "active", MaterialSpool.current_weight_kg > 0)
        .all()
    )
    names = {c.color_id: c for c in db.query(ShopColor)}
    result: Dict[int, dict] = {}
    for spool in spools:
        material = spool.product
        if material is None or material.color is None or not material.active:
            continue
        color = material.color
        custom = names.get(color.id)
        if custom and custom.hidden and not include_hidden:
            continue
        entry = result.get(material.id)
        if entry is None:
            mtype = material.material_type
            entry = result[material.id] = {
                "material_id": material.id,
                "color_id": color.id,
                "name": (custom.shop_name if custom and custom.shop_name else None) or color.name,
                "color_name": color.name,
                "hex": color.hex_code,
                "hex_secondary": color.hex_code_secondary,
                "material_code": mtype.code if mtype else None,
                "material": mtype.name if mtype else None,
                "brands": [],
                "remaining_g": 0.0,
                "hidden": bool(custom and custom.hidden),
            }
        entry["remaining_g"] += float(spool.current_weight_kg or 0)
        if spool.brand and spool.brand not in entry["brands"]:
            entry["brands"].append(spool.brand)
    colors = list(result.values())
    for entry in colors:
        entry["remaining_g"] = round(entry["remaining_g"], 1)
        entry["brands"].sort(key=str.lower)
    colors.sort(key=lambda c: ((c["material_code"] or "~"), c["name"].lower()))
    return colors


@router.put("/nebula/shops")
def sync_shop_stores(
    body: ShopStoresIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """La sincronización manda las tiendas y recibe en qué tiendas va cada artículo."""
    now = datetime.now(timezone.utc)
    if body.stores:  # una lista vacía sería un fallo de la tienda: no borrar nada
        wanted = {st.id: st for st in body.stores}
        for store in db.query(ShopStore).all():
            if store.id not in wanted:
                db.delete(store)
        for st in body.stores:
            store = db.get(ShopStore, st.id)
            if store is None:
                store = ShopStore(id=st.id)
                db.add(store)
            store.name = st.name
            store.domains = st.domains
            store.updated_at = now
        db.flush()

    if body.seed and db.query(ProductShopStore).first() is None:
        stores = {sid for (sid,) in db.query(ShopStore.id)}
        products = {pid for (pid,) in db.query(Product.id).filter(Product.id.in_(list(body.seed) or [0]))}
        for product_id, store_ids in body.seed.items():
            if product_id not in products:
                continue
            for store_id in set(store_ids) & stores:
                db.add(ProductShopStore(product_id=product_id, store_id=store_id))
    db.commit()
    return {"stores": db.query(ShopStore).count(), "assignments": _assignments(db)}


@router.get("/nebula/shop-catalog")
def shop_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Para la sincronización: tamaños y coste de caja de cada artículo y el precio del envío."""
    rows = db.query(ProductShopOption).all()
    boxes = {
        p.id: p
        for p in db.query(Product).filter(Product.id.in_([r.box_id for r in rows if r.box_id] or [0]))
    }
    return {
        "home_shipping_price": float(_settings(db).home_shipping_price),
        "options": {
            r.product_id: {
                "group_id": r.group_id,
                "size_label": r.size_label if r.group_id else None,
                "position": r.position or 0,
                "box_cost": float(box_cost(boxes.get(r.box_id))),
                "customization": r.customization or "none",
            }
            for r in rows
        },
        "colors": shop_colors(db),
    }


@router.get("/nebula/shop-settings")
def get_shop_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    settings = _settings(db)
    db.commit()
    return {"home_shipping_price": float(settings.home_shipping_price)}


@router.put("/nebula/shop-settings")
def put_shop_settings(
    body: ShopSettingsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Precio del envío a domicilio; las tiendas lo aplican en su próxima sincronización."""
    settings = _settings(db)
    settings.home_shipping_price = body.home_shipping_price.quantize(Decimal("0.01"))
    settings.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"home_shipping_price": float(settings.home_shipping_price)}


def _ref(p: Product) -> dict:
    return {"id": p.id, "sku": p.sku, "name": p.name}


@router.get("/{item_id}/shop-options")
def get_item_shop_options(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Tamaños del artículo (si agrupa otros), a qué producto pertenece (si es un tamaño) y su caja."""
    _product(db, item_id)
    option = db.get(ProductShopOption, item_id)
    group = db.get(Product, option.group_id) if option and option.group_id else None
    box = db.get(Product, option.box_id) if option and option.box_id else None
    sizes = (
        db.query(ProductShopOption, Product)
        .join(Product, Product.id == ProductShopOption.product_id)
        .filter(ProductShopOption.group_id == item_id)
        .order_by(ProductShopOption.position, Product.name)
        .all()
    )
    boxes = (
        db.query(Product)
        .filter(Product.item_type == "packaging", Product.active.is_(True))
        .order_by(Product.name)
        .all()
    )
    return {
        "group": _ref(group) if group else None,
        "size_label": option.size_label if group else None,
        "box_id": box.id if box else None,
        "box_cost": float(box_cost(box)),
        "customization": (option.customization if option else None) or "none",
        "sizes": [
            {
                **_ref(p),
                "size_label": o.size_label,
                "selling_price": float(p.selling_price) if p.selling_price is not None else None,
                "active": bool(p.active),
                "box_id": o.box_id,
            }
            for o, p in sizes
        ],
        "boxes": [{**_ref(b), "cost": float(box_cost(b))} for b in boxes],
    }


@router.put("/{item_id}/shop-sizes")
def put_item_shop_sizes(
    item_id: int,
    body: ShopSizesIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Sustituye los tamaños del artículo (en este orden); la tienda los aplica en su próxima sincronización."""
    _product(db, item_id)
    own = db.get(ProductShopOption, item_id)
    if own and own.group_id and body.sizes:
        group = db.get(Product, own.group_id)
        raise HTTPException(status_code=400, detail=f"Este artículo ya es un tamaño de «{group.name if group else own.group_id}»")

    labels = [s.size_label.strip() for s in body.sizes]
    if any(not label for label in labels):
        raise HTTPException(status_code=400, detail="Cada tamaño necesita un nombre")
    if len({label.lower() for label in labels}) != len(labels):
        raise HTTPException(status_code=400, detail="Hay dos tamaños con el mismo nombre")
    ids = [s.product_id for s in body.sizes]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Un artículo está repetido")
    if item_id in ids:
        raise HTTPException(status_code=400, detail="Un artículo no puede ser tamaño de sí mismo")

    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(ids or [0]))}
    heads = {
        gid for (gid,) in db.query(ProductShopOption.group_id).filter(ProductShopOption.group_id.in_(ids or [0]))
    }
    for pid in ids:
        product = products.get(pid)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Artículo {pid} no encontrado")
        if product.item_type != "finished_good":
            raise HTTPException(status_code=400, detail=f"«{product.name}» no es un producto terminado")
        if pid in heads:
            raise HTTPException(status_code=400, detail=f"«{product.name}» ya tiene sus propios tamaños")
        option = db.get(ProductShopOption, pid)
        if option and option.group_id and option.group_id != item_id:
            group = db.get(Product, option.group_id)
            raise HTTPException(
                status_code=400,
                detail=f"«{product.name}» ya es un tamaño de «{group.name if group else option.group_id}»",
            )

    for option in db.query(ProductShopOption).filter(ProductShopOption.group_id == item_id):
        if option.product_id not in ids:
            option.group_id = None
            option.size_label = None
            option.position = 0
    for position, (pid, label) in enumerate(zip(ids, labels)):
        option = _option(db, pid)
        option.group_id = item_id
        option.size_label = label
        option.position = position
    db.commit()
    return get_item_shop_options(item_id, db, current_user)


@router.put("/{item_id}/shop-box")
def put_item_shop_box(
    item_id: int,
    body: ShopBoxIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Caja del artículo: su coste se suma al precio en la tienda."""
    _product(db, item_id)
    if body.box_id is not None:
        box = db.get(Product, body.box_id)
        if box is None or box.item_type != "packaging":
            raise HTTPException(status_code=400, detail="La caja tiene que ser un artículo de embalaje")
    _option(db, item_id).box_id = body.box_id
    db.commit()
    return get_item_shop_options(item_id, db, current_user)


@router.put("/{item_id}/shop-customization")
def put_item_shop_customization(
    item_id: int,
    body: ShopCustomizationIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Qué elige el cliente en la tienda. Un tamaño usa la de su producto."""
    _product(db, item_id)
    own = db.get(ProductShopOption, item_id)
    if own and own.group_id and body.customization != "none":
        raise HTTPException(status_code=400, detail="Un tamaño usa la personalización de su producto")
    _option(db, item_id).customization = body.customization
    db.commit()
    return get_item_shop_options(item_id, db, current_user)


@router.get("/nebula/shop-colors")
def get_shop_colors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Colores con bobinas, también los ocultos, para ponerles nombre en la tienda."""
    return {"colors": shop_colors(db, include_hidden=True)}


@router.put("/nebula/shop-colors/{color_id}")
def put_shop_color(
    color_id: int,
    body: ShopColorIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Nombre del color en la tienda (vacío: el de PrintFlow) y si se oculta."""
    if db.get(Color, color_id) is None:
        raise HTTPException(status_code=404, detail="Color no encontrado")
    row = db.get(ShopColor, color_id)
    if row is None:
        row = ShopColor(color_id=color_id)
        db.add(row)
    row.shop_name = " ".join((body.shop_name or "").split()) or None
    row.hidden = body.hidden
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"color_id": color_id, "shop_name": row.shop_name, "hidden": row.hidden}


@router.get("/{item_id}/shops")
def get_item_shops(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    _product(db, item_id)
    selected = {
        sid for (sid,) in db.query(ProductShopStore.store_id).filter(ProductShopStore.product_id == item_id)
    }
    return {
        "stores": [
            {"id": st.id, "name": st.name, "domains": st.domains or [], "selected": st.id in selected}
            for st in db.query(ShopStore).order_by(ShopStore.name)
        ]
    }


@router.put("/{item_id}/shops")
def put_item_shops(
    item_id: int,
    body: ItemShopsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Tiendas en las que se vende el artículo; la tienda lo aplica en su próxima sincronización."""
    _product(db, item_id)
    known = {sid for (sid,) in db.query(ShopStore.id)}
    unknown = set(body.store_ids) - known
    if unknown:
        raise HTTPException(status_code=400, detail=f"Tienda desconocida: {', '.join(sorted(unknown))}")
    db.query(ProductShopStore).filter(ProductShopStore.product_id == item_id).delete(synchronize_session=False)
    for store_id in sorted(set(body.store_ids)):
        db.add(ProductShopStore(product_id=item_id, store_id=store_id))
    db.commit()
    return get_item_shops(item_id, db, current_user)
