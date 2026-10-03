"""PrintFlow: las cantidades de producción llegan al navegador como número.

Antes salían como texto "1.0000" y la pantalla lo pintaba tal cual: en español
se leía como mil unidades.
"""
from decimal import Decimal

BASE = "/api/v1/production-orders"


def test_detalle_y_lista_devuelven_numeros(client, db, make_product, make_production_order):
    product = make_product()
    po = make_production_order(product_id=product.id, quantity=Decimal("1"))
    db.flush()

    detail = client.get(f"{BASE}/{po.id}").json()
    assert detail["quantity_ordered"] == 1 and isinstance(detail["quantity_ordered"], (int, float))
    assert not isinstance(detail["quantity_completed"], str)

    r = client.get(f"{BASE}/", params={"limit": 200})
    data = r.json()
    items = data["items"] if isinstance(data, dict) else data
    row = next(i for i in items if i["id"] == po.id)
    assert row["quantity_ordered"] == 1


def test_decimales_se_conservan(client, db, make_product, make_production_order):
    product = make_product()
    po = make_production_order(product_id=product.id, quantity=Decimal("2.5"))
    db.flush()
    assert client.get(f"{BASE}/{po.id}").json()["quantity_ordered"] == 2.5
