"""PrintFlow: tamaños, cajas y envío de las tiendas online."""
from decimal import Decimal

from app.api.v1.endpoints.nebula_shops import box_cost
from app.models.nebula_product import ProductShopOption, ShopSettings


def _box(make_product, **kwargs):
    return make_product(item_type="packaging", name=kwargs.pop("name", "Caja 10x10"), **kwargs)


class TestShopSizes:
    def test_group_sizes_and_catalog(self, client, db, make_product):
        head = make_product(name="Bola de Navidad 2D")
        small = make_product(name="Bola 2D Pequeña", selling_price=Decimal("4"))
        big = make_product(name="Bola 2D Grande", selling_price=Decimal("8"))
        box = _box(make_product, average_cost=Decimal("0.75"))
        db.commit()

        res = client.put(f"/api/v1/items/{head.id}/shop-sizes", json={"sizes": [
            {"product_id": small.id, "size_label": " 6 cm "},
            {"product_id": big.id, "size_label": "10 cm"},
        ]})
        assert res.status_code == 200, res.text
        data = res.json()
        assert [(s["id"], s["size_label"]) for s in data["sizes"]] == [(small.id, "6 cm"), (big.id, "10 cm")]

        res = client.put(f"/api/v1/items/{big.id}/shop-box", json={"box_id": box.id})
        assert res.status_code == 200, res.text
        assert res.json()["group"]["id"] == head.id and res.json()["size_label"] == "10 cm"
        assert res.json()["box_cost"] == 0.75

        catalog = client.get("/api/v1/items/nebula/shop-catalog").json()
        assert catalog["options"][str(small.id)] == {"group_id": head.id, "size_label": "6 cm", "position": 0, "box_cost": 0.0}
        assert catalog["options"][str(big.id)] == {"group_id": head.id, "size_label": "10 cm", "position": 1, "box_cost": 0.75}

        # Quitar un tamaño lo saca del grupo pero conserva su caja
        res = client.put(f"/api/v1/items/{head.id}/shop-sizes", json={"sizes": [{"product_id": small.id, "size_label": "6 cm"}]})
        assert res.status_code == 200, res.text
        option = db.get(ProductShopOption, big.id)
        db.refresh(option)
        assert option.group_id is None and option.size_label is None and option.box_id == box.id

    def test_validation(self, client, db, make_product):
        head, other = make_product(), make_product()
        a, b = make_product(), make_product()
        material = make_product(item_type="material")
        db.commit()
        put = lambda item, sizes: client.put(f"/api/v1/items/{item}/shop-sizes", json={"sizes": sizes})

        assert put(head.id, [{"product_id": a.id, "size_label": "M"}, {"product_id": b.id, "size_label": "m"}]).status_code == 400
        assert put(head.id, [{"product_id": head.id, "size_label": "M"}]).status_code == 400
        assert put(head.id, [{"product_id": material.id, "size_label": "M"}]).status_code == 400
        assert put(head.id, [{"product_id": a.id, "size_label": ""}]).status_code == 422
        assert put(head.id, [{"product_id": a.id, "size_label": "M"}]).status_code == 200
        # a ya es de head; head no puede ser tamaño de otro ni a tener tamaños
        assert put(other.id, [{"product_id": a.id, "size_label": "M"}]).status_code == 400
        assert put(other.id, [{"product_id": head.id, "size_label": "M"}]).status_code == 400
        assert put(a.id, [{"product_id": b.id, "size_label": "M"}]).status_code == 400

    def test_box_must_be_packaging(self, client, db, make_product):
        item, not_box = make_product(), make_product()
        db.commit()
        assert client.put(f"/api/v1/items/{item.id}/shop-box", json={"box_id": not_box.id}).status_code == 400
        assert client.put(f"/api/v1/items/{item.id}/shop-box", json={"box_id": None}).status_code == 200


class TestBoxCost:
    def test_cost_order(self, make_product):
        assert box_cost(None) == Decimal("0")
        assert box_cost(_box(make_product, standard_cost=Decimal("1"))) == Decimal("1.00")
        assert box_cost(_box(make_product, standard_cost=Decimal("1"), average_cost=Decimal("0.5"))) == Decimal("0.50")
        assert box_cost(_box(make_product, cost_method="standard", standard_cost=Decimal("1"), average_cost=Decimal("0.5"))) == Decimal("1.00")


class TestShopSettings:
    def test_home_shipping_price(self, client, db):
        db.query(ShopSettings).delete()
        db.commit()
        assert client.get("/api/v1/items/nebula/shop-settings").json() == {"home_shipping_price": 0.0}
        res = client.put("/api/v1/items/nebula/shop-settings", json={"home_shipping_price": "5.954"})
        assert res.status_code == 200, res.text
        assert res.json() == {"home_shipping_price": 5.95}
        assert client.get("/api/v1/items/nebula/shop-catalog").json()["home_shipping_price"] == 5.95
        assert client.put("/api/v1/items/nebula/shop-settings", json={"home_shipping_price": -1}).status_code == 422
