"""PrintFlow: precio unitario según la cantidad pedida.

Cada artículo puede tener tramos ``(desde N unidades → precio unitario)``. El
precio de una cantidad es el del tramo más alto que alcanza; por debajo del
primero, el precio de venta normal del artículo.
"""
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.nebula_product import ProductPriceTier
from app.models.product import Product


def _dec(value, field: str) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=400, detail=f"{field}: número no válido ({value!r})")
    if not result.is_finite():
        raise HTTPException(status_code=400, detail=f"{field}: número no válido ({value!r})")
    return result


def tier_to_dict(tier: ProductPriceTier) -> dict:
    return {
        "id": tier.id,
        "min_quantity": float(tier.min_quantity),
        "unit_price": float(tier.unit_price),
        "label": tier.label,
    }


def list_tiers(db: Session, product_id: int) -> list[ProductPriceTier]:
    return (
        db.query(ProductPriceTier)
        .filter(ProductPriceTier.product_id == product_id)
        .order_by(ProductPriceTier.min_quantity)
        .all()
    )


def tiers_by_product(db: Session, product_ids: list[int] | None = None) -> dict[int, list[dict]]:
    query = db.query(ProductPriceTier)
    if product_ids is not None:
        if not product_ids:
            return {}
        query = query.filter(ProductPriceTier.product_id.in_(product_ids))
    result: dict[int, list[dict]] = {}
    for tier in query.order_by(ProductPriceTier.product_id, ProductPriceTier.min_quantity):
        result.setdefault(tier.product_id, []).append(tier_to_dict(tier))
    return result


def replace_tiers(db: Session, product: Product, tiers: list[dict]) -> list[ProductPriceTier]:
    """Sustituye los tramos del artículo por ``tiers`` (lista vacía = sin tramos).

    No hace commit: lo hace quien llama.
    """
    clean: dict[Decimal, tuple[Decimal, str | None]] = {}
    for raw in tiers:
        qty = _dec(raw.get("min_quantity"), "Cantidad")
        price = _dec(raw.get("unit_price"), "Precio")
        if qty < 1:
            raise HTTPException(status_code=400, detail="La cantidad de un tramo tiene que ser 1 o más")
        if price < 0:
            raise HTTPException(status_code=400, detail="El precio de un tramo no puede ser negativo")
        if qty in clean:
            raise HTTPException(status_code=400, detail=f"Hay dos tramos desde {qty.normalize()} unidades")
        label = (raw.get("label") or "").strip()[:100] or None
        clean[qty] = (price, label)

    db.query(ProductPriceTier).filter(ProductPriceTier.product_id == product.id).delete(
        synchronize_session=False
    )
    created = []
    for qty in sorted(clean):
        price, label = clean[qty]
        tier = ProductPriceTier(product_id=product.id, min_quantity=qty, unit_price=price, label=label)
        db.add(tier)
        created.append(tier)
    db.flush()
    return created


def price_for_quantity(db: Session, product: Product, quantity) -> Decimal:
    """Precio unitario de ``product`` para ``quantity`` unidades."""
    qty = Decimal(str(quantity or 0))
    tier = (
        db.query(ProductPriceTier)
        .filter(ProductPriceTier.product_id == product.id, ProductPriceTier.min_quantity <= qty)
        .order_by(ProductPriceTier.min_quantity.desc())
        .first()
    )
    if tier is not None:
        return Decimal(str(tier.unit_price))
    return Decimal(str(product.selling_price or 0))
