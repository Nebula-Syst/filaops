"""PrintFlow: el pedido creado con un cliente debe guardar ese cliente.

Upstream validaba customer_id pero no lo guardaba en el pedido (customer_id,
customer_name, customer_email y customer_phone quedaban vacíos), así que el
pedido aparecía sin cliente.
"""
import uuid
from decimal import Decimal

from app.models.sales_order import SalesOrder


def _create_order(client, product_id, customer_id=None):
    payload = {
        "lines": [{"product_id": product_id, "quantity": 2, "unit_price": "12.50"}],
        "source": "manual",
    }
    if customer_id is not None:
        payload["customer_id"] = customer_id
    r = client.post("/api/v1/sales-orders/", json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_pedido_guarda_el_cliente_sin_email(client, db, make_product):
    """El caso real: cliente con nombre y teléfono pero sin email."""
    product = make_product(selling_price=Decimal("12.50"))
    db.flush()
    name = f"Sonia {uuid.uuid4().hex[:6]}"
    c = client.post("/api/v1/admin/customers/", json={
        "first_name": name, "last_name": "Gordillo", "phone": "646989733",
    }).json()

    order = _create_order(client, product.id, c["id"])
    db.expire_all()
    so = db.get(SalesOrder, order["id"])
    assert so.customer_id == c["id"]
    assert so.customer_name == f"{name} Gordillo"
    assert so.customer_email is None
    assert so.customer_phone == "646989733"
    # y la API lo devuelve
    detail = client.get(f"/api/v1/sales-orders/{order['id']}").json()
    assert detail["customer_id"] == c["id"]


def test_pedido_con_empresa_y_email(client, db, make_product):
    product = make_product(selling_price=Decimal("12.50"))
    db.flush()
    email = f"taller-{uuid.uuid4().hex[:6]}@example.com"
    c = client.post("/api/v1/admin/customers/", json={
        "company_name": "Hermandad Cristo de la Sangre", "email": email,
    }).json()

    order = _create_order(client, product.id, c["id"])
    db.expire_all()
    so = db.get(SalesOrder, order["id"])
    assert so.customer_name == "Hermandad Cristo de la Sangre"
    assert so.customer_email == email


def test_pedido_sin_cliente_sigue_funcionando(client, db, make_product):
    product = make_product(selling_price=Decimal("12.50"))
    db.flush()
    order = _create_order(client, product.id)
    db.expire_all()
    so = db.get(SalesOrder, order["id"])
    assert so.customer_id is None and so.customer_name is None


def test_la_lista_de_pedidos_muestra_el_cliente(client, db, make_product):
    product = make_product(selling_price=Decimal("12.50"))
    db.flush()
    name = f"Paqui {uuid.uuid4().hex[:6]}"
    c = client.post("/api/v1/admin/customers/", json={"first_name": name}).json()
    order = _create_order(client, product.id, c["id"])

    r = client.get("/api/v1/sales-orders/", params={"include_fulfillment": "true", "limit": 200})
    assert r.status_code == 200, r.text
    data = r.json()
    items = data["items"] if isinstance(data, dict) else data
    row = next(o for o in items if o["id"] == order["id"])
    assert row["customer_id"] == c["id"]
    assert row["customer_name"] == name
