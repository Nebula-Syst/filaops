"""PrintFlow: borrar un pedido que ya tiene historial (eventos) no debe fallar.

Antes, SQLAlchemy intentaba poner order_events.sales_order_id / shipping_events.sales_order_id
a NULL al borrar el pedido y la BD lo rechazaba (NOT NULL) → error 500 en "Eliminar pedido".
"""
from decimal import Decimal

from app.models.order_event import OrderEvent
from app.models.shipping_event import ShippingEvent
from app.models.sales_order import SalesOrder

BASE_URL = "/api/v1/sales-orders"


def _add_history(db, so):
    db.add(OrderEvent(sales_order_id=so.id, event_type="created", title="Order created"))
    db.add(OrderEvent(sales_order_id=so.id, event_type="status_change", title="Cancelled"))
    db.flush()


def test_borrar_pedido_pendiente_con_eventos(client, db, make_sales_order, make_product):
    product = make_product(selling_price=Decimal("10.00"))
    so = make_sales_order(product_id=product.id, status="pending")
    db.flush()
    _add_history(db, so)
    so_id = so.id

    response = client.delete(f"{BASE_URL}/{so_id}")
    assert response.status_code == 204, response.text
    db.expire_all()
    assert db.get(SalesOrder, so_id) is None
    assert db.query(OrderEvent).filter(OrderEvent.sales_order_id == so_id).count() == 0


def test_borrar_pedido_cancelado_con_eventos_de_envio(client, db, make_sales_order, make_product):
    product = make_product(selling_price=Decimal("10.00"))
    so = make_sales_order(product_id=product.id, status="cancelled")
    db.flush()
    _add_history(db, so)
    db.add(ShippingEvent(sales_order_id=so.id, event_type="label_purchased", title="Label"))
    db.flush()
    so_id = so.id

    response = client.delete(f"{BASE_URL}/{so_id}")
    assert response.status_code == 204, response.text
    db.expire_all()
    assert db.query(ShippingEvent).filter(ShippingEvent.sales_order_id == so_id).count() == 0


def test_borrar_pedido_creado_por_la_api(client, db, make_product):
    """El caso real: el pedido creado desde la API ya registra el evento 'created'."""
    product = make_product(selling_price=Decimal("10.00"))
    db.flush()
    created = client.post(BASE_URL + "/", json={
        "product_id": product.id, "quantity": 1, "unit_price": "10.00", "source": "manual",
    })
    if created.status_code >= 400:  # esquema distinto: usar formato con líneas
        created = client.post(BASE_URL + "/", json={
            "lines": [{"product_id": product.id, "quantity": 1, "unit_price": "10.00"}],
            "source": "manual",
        })
    assert created.status_code in (200, 201), created.text
    so_id = created.json()["id"]
    assert db.query(OrderEvent).filter(OrderEvent.sales_order_id == so_id).count() >= 1

    response = client.delete(f"{BASE_URL}/{so_id}")
    assert response.status_code == 204, response.text
