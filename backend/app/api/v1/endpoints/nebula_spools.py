"""PrintFlow: bobinas de filamento agrupadas por taller, marca y color.

Rutas bajo /api/v1/spools/nebula (se registran antes que las de FilaOps para
que no las capture /spools/{spool_id}). Los pesos van en gramos, como en el
resto de la API de bobinas de FilaOps (aunque las columnas se llamen _kg).

Al dar de alta bobinas en un taller se suma su peso al stock del filamento en
ese taller, igual que FilaOps lo resta al ajustar el peso de una bobina; así el
stock de filamento cuadra con las bobinas.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.v1.deps import get_current_staff_user
from app.db.session import get_db
from app.models import MaterialSpool, Product, User
from app.models.inventory import InventoryLocation
from app.services import inventory_ledger
from app.services.inventory_helpers import is_material
from app.services.inventory_service import get_effective_cost_per_inventory_unit

router = APIRouter(prefix="/spools/nebula", tags=["spools"])

MAX_BULK = 50


def _clean_brand(db: Session, brand: Optional[str]) -> Optional[str]:
    """Sin espacios de más y con la grafía que ya exista ("elegoo" → "Elegoo")."""
    brand = " ".join((brand or "").split())
    if not brand:
        return None
    existing = (
        db.query(MaterialSpool.brand)
        .filter(func.lower(MaterialSpool.brand) == brand.lower())
        .order_by(MaterialSpool.id)
        .first()
    )
    return existing[0] if existing else brand


def _material_info(product: Product) -> dict:
    color = product.color
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "material": product.material_type.name if product.material_type else None,
        "color": color.name if color else None,
        "color_hex": color.hex_code if color else None,
    }


@router.get("/summary")
def spools_summary(
    include_empty: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Bobinas por taller → marca + filamento, con el peso que le queda a cada una."""
    query = db.query(MaterialSpool).options(
        joinedload(MaterialSpool.product).joinedload(Product.color),
        joinedload(MaterialSpool.product).joinedload(Product.material_type),
        joinedload(MaterialSpool.location),
    )
    if not include_empty:
        query = query.filter(MaterialSpool.status == "active")

    groups = defaultdict(lambda: defaultdict(list))
    locations = {}
    for spool in query.all():
        loc_id = spool.location_id or 0
        locations[loc_id] = spool.location.name if spool.location else None
        groups[loc_id][((spool.brand or "").lower(), spool.product_id)].append(spool)

    result = []
    for loc_id, by_key in groups.items():
        items = []
        for spools in by_key.values():
            first = spools[0]
            spools.sort(key=lambda s: float(s.current_weight_kg or 0))
            items.append({
                "brand": first.brand,
                **_material_info(first.product),
                "count": len(spools),
                "total_g": round(sum(float(s.current_weight_kg or 0) for s in spools), 1),
                "spools": [
                    {
                        "id": s.id,
                        "spool_number": s.spool_number,
                        "current_g": float(s.current_weight_kg or 0),
                        "initial_g": float(s.initial_weight_kg or 0),
                        "status": s.status,
                    }
                    for s in spools
                ],
            })
        items.sort(key=lambda i: ((i["brand"] or "~").lower(), (i["material"] or "").lower(), (i["color"] or i["name"]).lower()))
        result.append({
            "location_id": loc_id or None,
            "location_name": locations[loc_id],
            "count": sum(i["count"] for i in items),
            "total_g": round(sum(i["total_g"] for i in items), 1),
            "items": items,
        })
    result.sort(key=lambda l: (l["location_id"] is None, (l["location_name"] or "").lower()))

    brands = sorted({b for (b,) in db.query(MaterialSpool.brand).filter(MaterialSpool.brand.isnot(None)).distinct()}, key=str.lower)
    return {"locations": result, "brands": brands}


@router.get("/materials")
def spool_materials(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Filamentos que se pueden elegir al dar de alta bobinas."""
    products = (
        db.query(Product)
        .options(joinedload(Product.color), joinedload(Product.material_type))
        .filter(Product.active.is_(True), Product.item_type == "material")
        .order_by(Product.name)
        .all()
    )
    return [_material_info(p) for p in products]


class SpoolBulkIn(BaseModel):
    product_id: int
    brand: Optional[str] = Field(None, max_length=100)
    location_id: Optional[int] = None
    initial_g: float = Field(..., gt=0, le=100000)
    current_g: Optional[float] = Field(None, ge=0, le=100000)
    quantity: int = Field(1, ge=1, le=MAX_BULK)
    notes: Optional[str] = None


def _next_numbers(db: Session, count: int) -> list:
    """BOB-00001, BOB-00002… sin chocar con los que ya existan."""
    existing = {n for (n,) in db.query(MaterialSpool.spool_number).filter(MaterialSpool.spool_number.like("BOB-%"))}
    numbers, n = [], 1
    while len(numbers) < count:
        candidate = f"BOB-{n:05d}"
        if candidate not in existing:
            numbers.append(candidate)
        n += 1
    return numbers


@router.post("/bulk")
def create_spools(
    body: SpoolBulkIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Da de alta una o varias bobinas iguales (p. ej. 3 de 1 kg de Elegoo negro)."""
    product = db.get(Product, body.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Filamento no encontrado")
    if not is_material(product):
        raise HTTPException(status_code=400, detail="El artículo no es un filamento")
    if body.location_id is not None and db.get(InventoryLocation, body.location_id) is None:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    current = body.current_g if body.current_g is not None else body.initial_g
    if current > body.initial_g:
        raise HTTPException(status_code=400, detail="El peso actual no puede ser mayor que el inicial")

    brand = _clean_brand(db, body.brand)
    created = []
    for number in _next_numbers(db, body.quantity):
        spool = MaterialSpool(
            spool_number=number,
            product_id=product.id,
            brand=brand,
            initial_weight_kg=Decimal(str(body.initial_g)),
            current_weight_kg=Decimal(str(current)),
            status="active",
            location_id=body.location_id,
            notes=body.notes,
            created_by=current_user.email,
        )
        db.add(spool)
        created.append(spool)
    db.flush()
    if body.location_id is not None and current > 0:
        cost = get_effective_cost_per_inventory_unit(product)
        for spool in created:
            inventory_ledger.post(
                db,
                product_id=product.id,
                location_id=body.location_id,
                transaction_type="receipt",
                quantity_delta=Decimal(str(current)),
                cost_per_unit=cost,
                reference_type="spool_created",
                reference_id=spool.id,
                notes=f"Bobina {spool.spool_number} dada de alta",
                created_by=current_user.email,
            )
    db.commit()
    return {"created": [{"id": s.id, "spool_number": s.spool_number} for s in created]}


class SpoolBrandIn(BaseModel):
    brand: Optional[str] = Field(None, max_length=100)


@router.patch("/{spool_id}/brand")
def set_spool_brand(
    spool_id: int,
    body: SpoolBrandIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    spool = db.get(MaterialSpool, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Bobina no encontrada")
    spool.brand = _clean_brand(db, body.brand)
    db.commit()
    return {"id": spool.id, "brand": spool.brand}
