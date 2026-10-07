"""PrintFlow: al terminar la orden de trabajo, la línea del pedido queda lista.

Si la orden de trabajo solo estaba ligada al pedido (sin sales_order_line_id),
el pedido pasaba a "listo para enviar" pero la línea seguía con 0 asignado y la
pantalla decía "Faltan 1" / bloqueado.
"""
from decimal import Decimal

from app.models.production_order import ProductionOrder
from app.models.sales_order import SalesOrder

SO_URL = "/api/v1/sales-orders"
PO_URL = "/api/v1/production-orders"


def _paid_order(client, db, product, quantity=1):
    db.flush()
    so = client.post(SO_URL + "/", json={
        "lines": [{"product_id": product.id, "quantity": quantity, "unit_price": "10.00"}],
        "source": "manual",
        "delivery_method": "pickup",
    }).json()
    assert client.patch(f"{SO_URL}/{so['id']}/status", json={"status": "confirmed"}).status_code == 200
    assert client.patch(
        f"{SO_URL}/{so['id']}/payment", json={"payment_status": "paid", "payment_method": "cash"}
    ).status_code == 200
    return so


def _complete(client, wo_id, qty):
    assert client.post(f"{PO_URL}/{wo_id}/release").status_code == 200
    assert client.post(f"{PO_URL}/{wo_id}/start").status_code == 200
    r = client.post(f"{PO_URL}/{wo_id}/complete", json={"quantity_completed": qty})
    assert r.status_code == 200, r.text


def test_orden_ligada_solo_al_pedido_deja_la_linea_lista(client, db, make_product):
    product = make_product(selling_price=Decimal("10.00"))
    so = _paid_order(client, db, product)

    wo = client.post(PO_URL + "/", json={
        "product_id": product.id, "quantity_ordered": 1, "sales_order_id": so["id"],
    })
    assert wo.status_code == 200, wo.text
    assert wo.json()["sales_order_line_id"] is None
    _complete(client, wo.json()["id"], 1)

    db.expire_all()
    assert db.get(SalesOrder, so["id"]).status == "ready_to_ship"
    fs = client.get(f"{SO_URL}/{so['id']}/fulfillment-status").json()
    assert fs["summary"]["state"] == "ready_to_ship"
    assert fs["lines"][0]["shortage"] == 0
    assert fs["lines"][0]["quantity_allocated"] == 1.0
    assert client.get(f"{SO_URL}/{so['id']}/can-ship").json() == {"can_ship": True, "reasons": []}


def test_pedidos_ya_atascados_se_ven_listos(client, db, make_product):
    """Orden terminada antes del arreglo: la línea quedó con 0 guardado."""
    product = make_product(selling_price=Decimal("10.00"))
    so = _paid_order(client, db, product)
    wo = client.post(PO_URL + "/", json={
        "product_id": product.id, "quantity_ordered": 1, "sales_order_id": so["id"],
    }).json()
    _complete(client, wo["id"], 1)

    order = db.get(SalesOrder, so["id"])
    order.lines[0].allocated_quantity = Decimal("0")  # estado antiguo
    db.flush()

    fs = client.get(f"{SO_URL}/{so['id']}/fulfillment-status").json()
    assert fs["lines"][0]["is_ready"] is True


def test_orden_generada_desde_el_pedido_sigue_igual(client, db, make_product):
    product = make_product(selling_price=Decimal("10.00"))
    so = _paid_order(client, db, product, quantity=2)
    assert client.post(f"{SO_URL}/{so['id']}/generate-production-orders").status_code == 200
    wo = db.query(ProductionOrder).filter(ProductionOrder.sales_order_id == so["id"]).one()
    assert wo.sales_order_line_id is not None
    _complete(client, wo.id, 2)

    fs = client.get(f"{SO_URL}/{so['id']}/fulfillment-status").json()
    assert fs["lines"][0]["quantity_allocated"] == 2.0
    assert fs["summary"]["state"] == "ready_to_ship"
