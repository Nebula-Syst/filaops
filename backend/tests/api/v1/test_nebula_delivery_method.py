"""PrintFlow: un pedido se puede entregar en mano o recoger, no solo enviar.

Con delivery_method = local_delivery / pickup no hace falta dirección ni
transportista: "entregar" mueve el inventario como un envío y deja el pedido en
"delivered" sin número de seguimiento.
"""
from decimal import Decimal

from app.models.inventory import Inventory
from app.models.order_event import OrderEvent
from app.models.sales_order import SalesOrder
from app.services.inventory_service import get_or_create_default_location

BASE_URL = "/api/v1/sales-orders"


def _seed_inventory(db, product_id, on_hand=Decimal("100")):
    loc = get_or_create_default_location(db)
    inv = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.location_id == loc.id,
    ).first()
    if inv is None:
        inv = Inventory(
            product_id=product_id, location_id=loc.id,
            on_hand_quantity=on_hand, allocated_quantity=Decimal("0"),
        )
        db.add(inv)
    else:
        inv.on_hand_quantity = on_hand
    db.flush()
    return inv


def _ready_order(db, make_sales_order, make_product, delivery_method):
    product = make_product(selling_price=Decimal("10.00"))
    so = make_sales_order(product_id=product.id, status="ready_to_ship")
    so.delivery_method = delivery_method
    so.shipping_address_line1 = None
    so.shipping_city = None
    db.flush()
    _seed_inventory(db, product.id)
    return so, product


def test_crear_pedido_para_recoger_sin_direccion(client, db, make_product):
    product = make_product(selling_price=Decimal("10.00"))
    db.flush()
    response = client.post(BASE_URL + "/", json={
        "lines": [{"product_id": product.id, "quantity": 1, "unit_price": "10.00"}],
        "source": "manual",
        "delivery_method": "pickup",
    })
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["delivery_method"] == "pickup"
    assert data["shipping_address_line1"] is None


def test_pedido_sin_metodo_es_envio(client, db, make_product):
    product = make_product(selling_price=Decimal("10.00"))
    db.flush()
    response = client.post(BASE_URL + "/", json={
        "lines": [{"product_id": product.id, "quantity": 1, "unit_price": "10.00"}],
        "source": "manual",
    })
    assert response.status_code == 201, response.text
    assert response.json()["delivery_method"] == "ship"


def test_metodo_invalido_rechazado(client, db, make_product):
    product = make_product(selling_price=Decimal("10.00"))
    db.flush()
    response = client.post(BASE_URL + "/", json={
        "lines": [{"product_id": product.id, "quantity": 1, "unit_price": "10.00"}],
        "delivery_method": "teleport",
    })
    assert response.status_code == 422


def test_entregar_en_mano_sin_direccion_ni_transportista(client, db, make_sales_order, make_product):
    so, _ = _ready_order(db, make_sales_order, make_product, "local_delivery")

    response = client.post(f"{BASE_URL}/{so.id}/ship", json={"carrier": None})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["delivery_method"] == "local_delivery"
    assert data["tracking_number"] is None
    assert data["carrier"] is None

    db.expire_all()
    order = db.get(SalesOrder, so.id)
    assert order.status == "delivered"
    assert order.fulfillment_status == "delivered"
    assert order.shipped_at is not None and order.delivered_at is not None
    assert order.tracking_number is None and order.carrier is None
    assert all(line.shipped_quantity == line.quantity for line in order.lines)
    titles = [e.title for e in db.query(OrderEvent).filter(OrderEvent.sales_order_id == so.id)]
    assert "Order delivered in person" in titles


def test_recogida_descuenta_inventario(client, db, make_sales_order, make_product):
    so, product = _ready_order(db, make_sales_order, make_product, "pickup")
    qty = sum(Decimal(str(line.quantity)) for line in so.lines) or Decimal(str(so.quantity))

    response = client.post(f"{BASE_URL}/{so.id}/ship", json={})
    assert response.status_code == 200, response.text

    db.expire_all()
    inv = db.query(Inventory).filter(Inventory.product_id == product.id).first()
    assert Decimal(str(inv.on_hand_quantity)) == Decimal("100") - qty
    assert db.get(SalesOrder, so.id).status == "delivered"


def test_recogida_no_se_entrega_dos_veces(client, db, make_sales_order, make_product):
    so, _ = _ready_order(db, make_sales_order, make_product, "pickup")
    assert client.post(f"{BASE_URL}/{so.id}/ship", json={}).status_code == 200
    assert client.post(f"{BASE_URL}/{so.id}/ship", json={}).status_code == 409


def test_envio_sigue_exigiendo_direccion(client, db, make_sales_order, make_product):
    so, _ = _ready_order(db, make_sales_order, make_product, "ship")
    response = client.post(f"{BASE_URL}/{so.id}/ship", json={"carrier": "USPS"})
    assert response.status_code == 400
    assert "no shipping address" in response.json()["detail"].lower()


def test_can_ship_no_pide_direccion_en_recogida(client, db, make_sales_order, make_product):
    so, _ = _ready_order(db, make_sales_order, make_product, "pickup")
    response = client.get(f"{BASE_URL}/can-ship")
    assert response.status_code == 200
    assert response.json()[str(so.id)] == {"can_ship": True, "reasons": []}


def test_cambiar_metodo_de_entrega(client, db, make_sales_order, make_product):
    product = make_product(selling_price=Decimal("10.00"))
    so = make_sales_order(product_id=product.id, status="confirmed")
    db.flush()

    response = client.patch(f"{BASE_URL}/{so.id}/address", json={"delivery_method": "pickup"})
    assert response.status_code == 200, response.text
    assert response.json()["delivery_method"] == "pickup"
    events = db.query(OrderEvent).filter(
        OrderEvent.sales_order_id == so.id,
        OrderEvent.event_type == "delivery_method_updated",
    ).all()
    assert len(events) == 1 and events[0].new_value == "pickup"


def test_no_se_cambia_metodo_tras_entregar(client, db, make_sales_order, make_product):
    so, _ = _ready_order(db, make_sales_order, make_product, "pickup")
    assert client.post(f"{BASE_URL}/{so.id}/ship", json={}).status_code == 200

    response = client.patch(f"{BASE_URL}/{so.id}/address", json={"delivery_method": "ship"})
    assert response.status_code == 409
