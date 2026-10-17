"""PrintFlow: pedidos servidos desde el stock y estado de los entregados."""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.production_order import ProductionOrder
from app.schemas.fulfillment_status import FulfillmentState
from app.services import sales_order_service
from app.services.fulfillment_status import get_fulfillment_status
from app.services.nebula_stock import reserve_stock, stock_coverage
from app.services.status_sync_service import sync_on_production_complete
from tests.services.test_blocking_audit_services import _make_inventory, _make_order_line


def _order(make_sales_order, product, qty, status="confirmed", **kwargs):
    return make_sales_order(
        product_id=product.id, quantity=qty, status=status, order_type="line_item", **kwargs
    )


def _line(db, so, product, qty, **kwargs):
    line = _make_order_line(db, so.id, product.id, quantity=Decimal(str(qty)), **kwargs)
    db.refresh(so)
    return line


class TestStockCoverage:
    def test_enough_stock_needs_no_production(self, db, make_product, make_sales_order):
        product = make_product()
        _make_inventory(db, product.id, Decimal("11"))
        so = _order(make_sales_order, product, 8)
        _line(db, so, product, 8)

        coverage = stock_coverage(db, so)
        assert coverage["fully_covered"] is False  # aún no apartado
        assert coverage["stock_covers_all"] is True
        assert coverage["can_reserve"] is True
        assert coverage["lines"][0]["from_stock"] == 8
        assert coverage["lines"][0]["to_make"] == 0

    def test_reserve_moves_order_to_ready_to_ship(self, db, make_product, make_sales_order):
        product = make_product()
        _make_inventory(db, product.id, Decimal("11"))
        so = _order(make_sales_order, product, 8)
        line = _line(db, so, product, 8)

        coverage = reserve_stock(db, so)

        assert coverage["fully_covered"] is True
        assert so.status == "ready_to_ship"
        assert line.allocated_quantity == Decimal("8")
        assert line.stock_allocated_quantity == Decimal("8")
        status = get_fulfillment_status(db, so.id)
        assert status.summary.state == FulfillmentState.READY_TO_SHIP

    def test_other_open_orders_keep_their_units(self, db, make_product, make_sales_order):
        product = make_product()
        _make_inventory(db, product.id, Decimal("11"))
        first = _order(make_sales_order, product, 8)
        _line(db, first, product, 8)
        reserve_stock(db, first)

        second = _order(make_sales_order, product, 5)
        _line(db, second, product, 5)
        coverage = stock_coverage(db, second)

        assert coverage["lines"][0]["from_stock"] == 3
        assert coverage["lines"][0]["to_make"] == 2

    def test_cannot_reserve_before_confirmation(self, db, make_product, make_sales_order):
        product = make_product()
        _make_inventory(db, product.id, Decimal("5"))
        so = _order(make_sales_order, product, 2, status="pending")
        _line(db, so, product, 2)
        with pytest.raises(HTTPException):
            reserve_stock(db, so)


class TestGenerateProductionUsesStock:
    def test_full_stock_creates_no_work_order(self, db, make_product, make_sales_order):
        product = make_product(has_bom=True)
        _make_inventory(db, product.id, Decimal("10"))
        so = _order(make_sales_order, product, 4)
        _line(db, so, product, 4)

        result = sales_order_service.generate_production_orders(db, so.id, "qa@test")

        assert result["created_orders"] == []
        assert so.status == "ready_to_ship"
        assert db.query(ProductionOrder).filter_by(sales_order_id=so.id).count() == 0

    def test_partial_stock_makes_only_the_shortfall(self, db, make_product, make_sales_order):
        product = make_product(has_bom=True)
        _make_inventory(db, product.id, Decimal("3"))
        so = _order(make_sales_order, product, 8, payment_status="paid")
        line = _line(db, so, product, 8)

        result = sales_order_service.generate_production_orders(db, so.id, "qa@test")

        assert len(result["created_orders"]) == 1
        wo = db.query(ProductionOrder).filter_by(sales_order_id=so.id).one()
        assert wo.quantity_ordered == Decimal("5")
        assert line.stock_allocated_quantity == Decimal("3")
        assert so.status == "in_production"

        # Al terminar la orden, lo fabricado se suma a lo apartado del stock
        wo.status = "complete"
        wo.quantity_completed = Decimal("5")
        db.flush()
        sync_on_production_complete(db, wo)
        assert line.allocated_quantity == Decimal("8")
        assert so.status == "ready_to_ship"


class TestDeliveredOrdersInList:
    @pytest.mark.parametrize("status", ["delivered", "completed"])
    def test_delivered_order_is_not_ready_to_ship(
        self, db, make_product, make_sales_order, status
    ):
        product = make_product()
        so = _order(make_sales_order, product, 2, status=status)
        _line(db, so, product, 2, shipped_quantity=Decimal("2"))

        result = get_fulfillment_status(db, so.id)

        assert result.summary.state == FulfillmentState.SHIPPED
        assert result.summary.can_ship_complete is False
