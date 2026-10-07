"""
Status Sync Service - Auto-update parent entities when children complete

This module handles automatic status transitions:
- SalesOrder status updates when all ProductionOrders complete
- Fulfillment status updates when production is ready
- Sales order line allocated_quantity updates when production completes

Triggered by production_orders.py when a PO is completed.
"""
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.sales_order import SalesOrder, SalesOrderLine
from app.models.production_order import ProductionOrder
from app.logging_config import get_logger

logger = get_logger(__name__)


_COMPLETED_PO_STATUSES = ("complete", "completed", "closed")


def compute_production_allocations(
    db: Session, sales_order_id: int, lines: list
) -> dict:
    """Completed production quantity per sales order line: {line_id: Decimal}.

    Work orders linked to a line count for that line. Work orders linked only to
    the order (sales_order_line_id NULL) count for the order's lines with the
    same product, in line order and capped at each line's quantity. Only lines
    that some completed work order feeds appear in the result.
    """
    completed_pos = db.query(
        ProductionOrder.sales_order_line_id,
        ProductionOrder.product_id,
        func.coalesce(func.sum(ProductionOrder.quantity_completed), 0),
    ).filter(
        ProductionOrder.sales_order_id == sales_order_id,
        ProductionOrder.status.in_(_COMPLETED_PO_STATUSES),
    ).group_by(
        ProductionOrder.sales_order_line_id, ProductionOrder.product_id
    ).all()

    by_line: dict = {}
    unlinked_by_product: dict = {}
    for line_id, product_id, qty in completed_pos:
        qty = Decimal(str(qty or 0))
        if line_id is not None:
            by_line[line_id] = by_line.get(line_id, Decimal("0")) + qty
        elif product_id is not None:
            unlinked_by_product[product_id] = (
                unlinked_by_product.get(product_id, Decimal("0")) + qty
            )

    allocations: dict = {}
    for line in sorted(lines, key=lambda ln: ln.id):
        allocated = by_line.get(line.id)
        pool = unlinked_by_product.get(line.product_id) if line.product_id else None
        if allocated is None and not pool:
            continue
        allocated = allocated or Decimal("0")
        if pool:
            room = max(Decimal("0"), Decimal(str(line.quantity or 0)) - allocated)
            take = min(room, pool)
            allocated += take
            unlinked_by_product[line.product_id] = pool - take
        allocations[line.id] = allocated
    return allocations


def sync_on_production_complete(db: Session, production_order: ProductionOrder) -> bool:
    """
    Called when a production order is completed.
    Updates parent SalesOrder if ALL production orders for it are done.
    Also updates allocated_quantity on the linked sales order line.

    Args:
        db: Database session
        production_order: The just-completed production order

    Returns:
        True if SalesOrder was updated, False otherwise
    """
    if not production_order.sales_order_id:
        return False

    sales_order = db.query(SalesOrder).filter(
        SalesOrder.id == production_order.sales_order_id
    ).first()

    if not sales_order:
        logger.warning(
            f"Production order {production_order.code} references non-existent "
            f"sales order {production_order.sales_order_id}"
        )
        return False

    updated = False

    # Update allocated_quantity on the sales order lines this production fed.
    # This reflects that production has created inventory ready to ship.
    # PrintFlow: also counts work orders linked only to the order (no
    # sales_order_line_id), matched to the line by product — before, those left
    # the line at 0 ("Short 1") even though the order moved to ready_to_ship.
    lines = db.query(SalesOrderLine).filter(
        SalesOrderLine.sales_order_id == sales_order.id
    ).all()
    allocations = compute_production_allocations(db, sales_order.id, lines)
    for line in lines:
        if line.id not in allocations:
            continue
        old_allocated = Decimal(str(line.allocated_quantity or 0))
        new_allocated = allocations[line.id]
        if new_allocated != old_allocated:
            line.allocated_quantity = new_allocated
            logger.info(
                f"Updated SO line {line.id} allocated_quantity: {old_allocated} -> {new_allocated} "
                f"(from production order {production_order.code})"
            )
            updated = True

    # Get all production orders for this sales order
    all_production_orders = db.query(ProductionOrder).filter(
        ProductionOrder.sales_order_id == sales_order.id
    ).all()

    if not all_production_orders:
        return updated

    # Check if ALL are complete or closed
    # Note: production orders use "complete" (not "completed")
    completed_statuses = {"complete", "completed", "closed"}
    all_complete = all(
        po.status in completed_statuses for po in all_production_orders
    )

    if not all_complete:
        return updated

    # All production orders complete - update sales order

    # Update fulfillment_status if pending
    if sales_order.fulfillment_status == "pending":
        sales_order.fulfillment_status = "ready"
        logger.info(
            f"Auto-updated {sales_order.order_number} fulfillment_status to 'ready' "
            f"(all {len(all_production_orders)} production orders complete)"
        )
        updated = True

    # Update order status if it's in a pre-shipping state
    # Valid states that can transition to ready_to_ship when production completes
    pre_ship_statuses = {"pending", "confirmed", "in_production"}
    if sales_order.status in pre_ship_statuses:
        old_status = sales_order.status
        sales_order.status = "ready_to_ship"
        logger.info(
            f"Auto-updated {sales_order.order_number} status from '{old_status}' to 'ready_to_ship' "
            f"(all {len(all_production_orders)} production orders complete)"
        )
        updated = True

    return updated


def check_sales_order_production_status(db: Session, sales_order_id: int) -> dict:
    """
    Check the production status for a sales order.

    Args:
        db: Database session
        sales_order_id: ID of the sales order

    Returns:
        Dict with production status info
    """
    production_orders = db.query(ProductionOrder).filter(
        ProductionOrder.sales_order_id == sales_order_id
    ).all()

    if not production_orders:
        return {
            "has_production_orders": False,
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "pending": 0,
            "all_complete": False,
        }

    # Note: production orders use "complete" (not "completed")
    completed = sum(1 for po in production_orders if po.status in ("complete", "completed", "closed"))
    in_progress = sum(1 for po in production_orders if po.status in ("in_progress", "short"))
    pending = sum(1 for po in production_orders if po.status in ("pending", "scheduled", "draft", "released"))

    return {
        "has_production_orders": True,
        "total": len(production_orders),
        "completed": completed,
        "in_progress": in_progress,
        "pending": pending,
        "all_complete": completed == len(production_orders),
    }
