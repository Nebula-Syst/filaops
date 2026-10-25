"""PrintFlow: en qué tiendas online se vende cada artículo.

Las tiendas (Medusa) mandan su lista en cada sincronización y reciben en qué
tiendas va cada artículo: se elige en PrintFlow y la tienda lo obedece. La
primera vez la tienda manda lo que ya tenía, para no vaciarla.

Rutas bajo /api/v1/items (se registran antes que las de FilaOps para que
/items/nebula/... no choque con /items/{item_id}).
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_staff_user
from app.db.session import get_db
from app.models.nebula_product import ProductShopStore, ShopStore
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


def _assignments(db: Session) -> Dict[int, List[str]]:
    result: Dict[int, List[str]] = {}
    for row in db.query(ProductShopStore).order_by(ProductShopStore.product_id, ProductShopStore.store_id):
        result.setdefault(row.product_id, []).append(row.store_id)
    return result


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
