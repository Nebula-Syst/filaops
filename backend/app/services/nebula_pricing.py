"""PrintFlow: precio unitario según la cantidad pedida.

Cada artículo puede tener tramos ``(desde N unidades → precio unitario)``.

- Sin piezas por cama: el precio de una cantidad es el del tramo más alto que
  alcanza; por debajo del primero, el precio de venta normal del artículo.
- Con piezas por cama (``Product.units_per_bed``): se imprime por camas, así que
  el pedido se reparte en camas llenas más una con el resto, y cada cama cobra
  por pieza el tramo de las piezas que lleva. Nazareno, 4 por cama, tramos
  1→39, 2→30, 3→27, 4→25: 5 uds = 4×25 + 1×39 = 139 €.
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


def _tier_price(product: Product, tiers: list[ProductPriceTier], qty: Decimal) -> Decimal:
    price = Decimal(str(product.selling_price or 0))
    for tier in tiers:  # ordenados por cantidad
        if tier.min_quantity <= qty:
            price = Decimal(str(tier.unit_price))
    return price


def price_breakdown(db: Session, product: Product, quantity) -> list[dict]:
    """Cómo se cobra ``quantity``: [{quantity, unit_price, beds, bed_size, full}].

    Sin piezas por cama es una sola parte. Con piezas por cama, una parte para
    las camas llenas y otra para la cama del resto (si la hay).
    """
    qty = Decimal(str(quantity or 0))
    tiers = list_tiers(db, product.id)
    per_bed = product.units_per_bed
    if not per_bed or qty <= 0 or qty != qty.to_integral_value():
        return [{"quantity": qty, "unit_price": _tier_price(product, tiers, qty), "beds": None, "bed_size": None, "full": None}]

    size = Decimal(per_bed)
    full_beds = int(qty // size)
    rest = qty - full_beds * size
    parts = []
    if full_beds:
        parts.append({
            "quantity": full_beds * size,
            "unit_price": _tier_price(product, tiers, size),
            "beds": full_beds,
            "bed_size": per_bed,
            "full": True,
        })
    if rest:
        parts.append({
            "quantity": rest,
            "unit_price": _tier_price(product, tiers, rest),
            "beds": 1,
            "bed_size": int(rest),
            "full": False,
        })
    return parts


def price_for_quantity(db: Session, product: Product, quantity) -> Decimal:
    """Precio unitario (medio, si va por camas) de ``product`` para ``quantity``."""
    parts = price_breakdown(db, product, quantity)
    qty = sum((p["quantity"] for p in parts), Decimal("0"))
    if qty <= 0 or len(parts) == 1:
        return parts[0]["unit_price"]
    total = sum((p["quantity"] * p["unit_price"] for p in parts), Decimal("0"))
    return total / qty


def pricing_by_product(db: Session, product_ids: list[int] | None = None) -> dict[int, dict]:
    """{product_id: {units_per_bed, tiers}} de los artículos con tramos o piezas por cama."""
    tiers = tiers_by_product(db, product_ids)
    query = db.query(Product.id, Product.units_per_bed).filter(Product.units_per_bed.isnot(None))
    if product_ids is not None:
        query = query.filter(Product.id.in_(product_ids or [-1]))
    beds = dict(query.all())
    return {
        pid: {"units_per_bed": beds.get(pid), "tiers": tiers.get(pid, [])}
        for pid in set(tiers) | set(beds)
    }


def bed_part_note(part: dict) -> str | None:
    """Texto para la línea del pedido: "2 camas completas (4 por cama)", "1 cama con 1"."""
    if not part.get("beds"):
        return None
    if part.get("full"):
        beds = part["beds"]
        word = "cama completa" if beds == 1 else "camas completas"
        return f"{beds} {word} ({part['bed_size']} por cama)"
    return f"1 cama con {part['bed_size']}"
