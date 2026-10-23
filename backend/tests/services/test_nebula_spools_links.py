"""PrintFlow: bobinas por taller con marca y enlaces de los artículos en las tiendas."""
from decimal import Decimal

from app.models import MaterialSpool
from app.models.inventory import Inventory, InventoryLocation
from app.models.nebula_product import ProductShopLink


def _location(db, name="Taller prueba"):
    location = InventoryLocation(name=name, code=name.upper().replace(" ", "-"), type="warehouse", active=True)
    db.add(location)
    db.flush()
    return location


def _material(make_product):
    return make_product(item_type="material", unit="G", purchase_uom="KG", purchase_factor=1000, name="PLA - Black")


class TestSpools:
    def test_bulk_create_groups_and_adds_stock(self, client, db, make_product):
        material = _material(make_product)
        location = _location(db)
        db.commit()

        res = client.post("/api/v1/spools/nebula/bulk", json={
            "product_id": material.id, "brand": " Elegoo ", "location_id": location.id,
            "initial_g": 1000, "quantity": 2,
        })
        assert res.status_code == 200, res.text
        assert len(res.json()["created"]) == 2
        res = client.post("/api/v1/spools/nebula/bulk", json={
            "product_id": material.id, "brand": "elegoo", "location_id": location.id,
            "initial_g": 1000, "current_g": 100,
        })
        assert res.status_code == 200, res.text

        numbers = {s.spool_number for s in db.query(MaterialSpool).filter_by(product_id=material.id)}
        assert len(numbers) == 3 and all(n.startswith("BOB-") for n in numbers)

        stock = db.query(Inventory).filter_by(product_id=material.id, location_id=location.id).one()
        assert stock.on_hand_quantity == Decimal("2100")

        summary = client.get("/api/v1/spools/nebula/summary").json()
        assert summary["brands"] == ["Elegoo"]
        loc = next(l for l in summary["locations"] if l["location_id"] == location.id)
        # "Elegoo" y "elegoo" son la misma marca: un solo grupo con 3 bobinas
        assert len(loc["items"]) == 1
        item = loc["items"][0]
        assert item["count"] == 3 and item["total_g"] == 2100
        assert [s["current_g"] for s in item["spools"]] == [100, 1000, 1000]

    def test_validation(self, client, db, make_product):
        material = _material(make_product)
        finished = make_product()
        db.commit()
        assert client.post("/api/v1/spools/nebula/bulk", json={"product_id": finished.id, "initial_g": 1000}).status_code == 400
        assert client.post("/api/v1/spools/nebula/bulk", json={"product_id": material.id, "initial_g": 500, "current_g": 900}).status_code == 400
        assert client.post("/api/v1/spools/nebula/bulk", json={"product_id": material.id, "initial_g": 500, "quantity": 51}).status_code == 422

    def test_brand_edit_and_list(self, client, db, make_product):
        material = _material(make_product)
        db.commit()
        spool_id = client.post("/api/v1/spools/nebula/bulk", json={"product_id": material.id, "initial_g": 1000}).json()["created"][0]["id"]
        assert client.patch(f"/api/v1/spools/nebula/{spool_id}/brand", json={"brand": "Bambu Lab"}).json()["brand"] == "Bambu Lab"
        listed = client.get(f"/api/v1/spools/?product_id={material.id}").json()["items"]
        assert listed[0]["brand"] == "Bambu Lab"
        materials = client.get("/api/v1/spools/nebula/materials").json()
        assert any(m["product_id"] == material.id for m in materials)


class TestShopLinks:
    def test_replace_and_read(self, client, db, make_product):
        a, b = make_product(), make_product()
        db.commit()
        res = client.put("/api/v1/items/nebula/shop-links", json={"links": {
            str(a.id): [{"store": "Los Aliados", "url": "https://glprintworks.com/es/products/a"}],
            str(b.id): [{"store": "Los Aliados", "url": "https://glprintworks.com/es/products/b"}],
            "999999": [{"store": "X", "url": "https://x"}],
        }})
        assert res.status_code == 200, res.text
        assert res.json()["links"] == 2
        assert client.get(f"/api/v1/items/{a.id}/shop-links").json() == [
            {"store": "Los Aliados", "url": "https://glprintworks.com/es/products/a"},
        ]

        # La siguiente sincronización sustituye todo
        client.put("/api/v1/items/nebula/shop-links", json={"links": {str(b.id): []}})
        assert client.get(f"/api/v1/items/{a.id}/shop-links").json() == []
        assert db.query(ProductShopLink).count() == 0

    def test_rejects_non_http(self, client, db, make_product):
        a = make_product()
        db.commit()
        res = client.put("/api/v1/items/nebula/shop-links", json={"links": {str(a.id): [{"store": "S", "url": "javascript:alert(1)"}]}})
        assert res.status_code == 422
