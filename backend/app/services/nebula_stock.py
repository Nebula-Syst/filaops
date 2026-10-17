"""PrintFlow: servir pedidos desde el stock de producto terminado.

En FilaOps un pedido solo llega a "listo para enviar" cuando terminan sus
órdenes de trabajo, aunque el producto ya esté en el almacén. Aquí:

- ``stock_coverage`` calcula, línea a línea, cuánto se puede servir con el stock
  libre y cuánto hay que fabricar.
- ``reserve_stock`` aparta ese stock para las líneas (allocated_quantity +
  stock_allocated_quantity) y, si con eso el pedido queda cubierto y no tiene
  órdenes de trabajo abiertas, lo pasa a "ready_to_ship".

Stock libre de un producto = existencias − reservado en inventario (materiales
para fabricar) − lo ya apartado o fabricado para otros pedidos abiertos. El
inventario no se mueve hasta la entrega, igual que con lo fabricado; ship_order()
vuelve a comprobar las existencias con la fila bloqueada.
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.production_order import ProductionOrder
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.services.sales_order_shared import record_order_event

ZERO = Decimal("0")
CLOSED_ORDER_STATUSES = ("shipped", "delivered", "completed", "cancelled")
_DONE_WO_STATUSES = ("complete", "completed", "closed", "cancelled")
RESERVABLE_ORDER_STATUSES = ("confirmed", "in_production")


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def _stock_lines(order: SalesOrder) -> list:
    return sorted(
        (
            line
            for line in order.lines
            if line.product_id and (line.line_type or "product") == "product"
        ),
        key=lambda ln: ln.id,
    )


def free_stock(db: Session, product_ids: set) -> dict:
    """Unidades libres por producto (todas las ubicaciones)."""
    if not product_ids:
        return {}
    rows = (
        db.query(
            Inventory.product_id,
            func.coalesce(func.sum(Inventory.on_hand_quantity), 0),
            func.coalesce(func.sum(Inventory.allocated_quantity), 0),
        )
        .filter(Inventory.product_id.in_(product_ids))
        .group_by(Inventory.product_id)
        .all()
    )
    free = {pid: ZERO for pid in product_ids}
    for pid, on_hand, allocated in rows:
        free[pid] = _d(on_hand) - _d(allocated)

    # Lo que ya es de algún pedido abierto (apartado de stock o fabricado para
    # él y todavía sin entregar), incluido este: lo suyo cuenta como "ready"
    committed = (
        db.query(SalesOrderLine)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .filter(
            SalesOrderLine.product_id.in_(product_ids),
            SalesOrder.status.notin_(CLOSED_ORDER_STATUSES),
        )
        .all()
    )
    for line in committed:
        pending = max(ZERO, _d(line.quantity) - _d(line.shipped_quantity))
        free[line.product_id] -= min(pending, _d(line.allocated_quantity))

    return {pid: max(ZERO, qty) for pid, qty in free.items()}


def _open_production_by_line(db: Session, order: SalesOrder) -> tuple[dict, dict]:
    """Cantidad en órdenes de trabajo abiertas: (por línea, sin línea por producto)."""
    rows = (
        db.query(
            ProductionOrder.sales_order_line_id,
            ProductionOrder.product_id,
            func.coalesce(func.sum(ProductionOrder.quantity_ordered), 0),
        )
        .filter(
            ProductionOrder.sales_order_id == order.id,
            ProductionOrder.status.notin_(_DONE_WO_STATUSES),
        )
        .group_by(ProductionOrder.sales_order_line_id, ProductionOrder.product_id)
        .all()
    )
    by_line, by_product = {}, {}
    for line_id, product_id, qty in rows:
        if line_id is not None:
            by_line[line_id] = by_line.get(line_id, ZERO) + _d(qty)
        elif product_id is not None:
            by_product[product_id] = by_product.get(product_id, ZERO) + _d(qty)
    return by_line, by_product


def stock_coverage(db: Session, order: SalesOrder) -> dict:
    """Qué parte de cada línea sale del stock y qué parte hay que fabricar."""
    lines = _stock_lines(order)
    free = free_stock(db, {ln.product_id for ln in lines})
    wo_by_line, wo_by_product = _open_production_by_line(db, order)

    result = []
    for line in lines:
        remaining = max(ZERO, _d(line.quantity) - _d(line.shipped_quantity))
        ready = min(remaining, _d(line.allocated_quantity))
        in_production = wo_by_line.get(line.id, ZERO)
        pool = wo_by_product.get(line.product_id, ZERO)
        if pool:
            take = min(pool, max(ZERO, remaining - ready - in_production))
            in_production += take
            wo_by_product[line.product_id] = pool - take
        need = max(ZERO, remaining - ready - in_production)
        from_stock = min(need, free.get(line.product_id, ZERO))
        free[line.product_id] = free.get(line.product_id, ZERO) - from_stock
        result.append({
            "line_id": line.id,
            "product_id": line.product_id,
            "product_sku": line.product.sku if line.product else None,
            "quantity": float(remaining),
            "ready": float(ready),
            "stock_allocated": float(min(ready, _d(line.stock_allocated_quantity))),
            "in_production": float(in_production),
            "from_stock": float(from_stock),
            "to_make": float(need - from_stock),
        })

    return {
        "order_id": order.id,
        "status": order.status,
        "can_reserve": order.status in RESERVABLE_ORDER_STATUSES
        and any(ln["from_stock"] > 0 for ln in result),
        # Todo apartado ya (listo para entregar sin fabricar más)
        "fully_covered": bool(result)
        and all(ln["ready"] >= ln["quantity"] for ln in result),
        # Con el stock libre basta para todo lo que falta
        "stock_covers_all": bool(result)
        and any(ln["from_stock"] > 0 for ln in result)
        and all(ln["to_make"] == 0 and ln["in_production"] == 0 for ln in result),
        "from_stock": float(sum(_d(ln["from_stock"]) for ln in result)),
        "to_make": float(sum(_d(ln["to_make"]) for ln in result)),
        "lines": result,
    }


def reserve_stock(db: Session, order: SalesOrder, user_id=None) -> dict:
    """Aparta el stock libre para las líneas del pedido.

    Devuelve la cobertura resultante. Si todo queda cubierto y no hay órdenes
    de trabajo abiertas, el pedido pasa a "ready_to_ship".
    """
    if order.status not in RESERVABLE_ORDER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Stock can only be used once the order is confirmed and before it ships; "
                f"this order is {order.status.replace('_', ' ')}."
            ),
        )

    # Bloquear las filas de inventario de estos productos para que dos pedidos
    # a la vez no se lleven las mismas unidades
    product_ids = {ln.product_id for ln in _stock_lines(order)}
    if product_ids and db.bind is not None and db.bind.dialect.name == "postgresql":
        db.query(Inventory.id).filter(
            Inventory.product_id.in_(product_ids)
        ).with_for_update().all()

    coverage = stock_coverage(db, order)
    lines_by_id = {ln.id: ln for ln in order.lines}
    taken = ZERO
    for item in coverage["lines"]:
        qty = _d(item["from_stock"])
        if qty <= 0:
            continue
        line = lines_by_id[item["line_id"]]
        line.allocated_quantity = _d(line.allocated_quantity) + qty
        line.stock_allocated_quantity = _d(line.stock_allocated_quantity) + qty
        taken += qty

    if taken > 0:
        record_order_event(
            db=db,
            order_id=order.id,
            event_type="status_change",
            title="Reserved from stock",
            description=f"{taken.normalize():f} unit(s) taken from finished-goods stock",
            user_id=user_id,
        )

    db.flush()
    coverage = stock_coverage(db, order)
    if coverage["fully_covered"]:
        order.status = "ready_to_ship"
        if order.fulfillment_status == "pending":
            order.fulfillment_status = "ready"
    return coverage

