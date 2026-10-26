"""PrintFlow: colores y personalización de las tiendas online."""
import uuid
from decimal import Decimal

from app.models.material import Color
from app.models.material_spool import MaterialSpool


def _color(db, name, hex_code="#FF0000"):
    color = Color(code=f"T-{uuid.uuid4().hex[:8]}", name=name, hex_code=hex_code, active=True)
    db.add(color)
    db.flush()
    return color


def _spool(db, material, grams, brand=None, status="active"):
    spool = MaterialSpool(
        spool_number=f"T-{uuid.uuid4().hex[:10]}",
        product_id=material.id,
        brand=brand,
        initial_weight_kg=Decimal("1000"),
        current_weight_kg=Decimal(str(grams)),
        status=status,
    )
    db.add(spool)
    return spool


def _mine(colors, *materials):
    ids = {m.id for m in materials}
    return {c["material_id"]: c for c in colors if c["material_id"] in ids}


class TestShopColors:
    def test_colors_from_spools(self, client, db, make_product):
        red, blue, green = _color(db, "Red"), _color(db, "Blue", "#0000FF"), _color(db, "Green")
        pla_red = make_product(item_type="material", color_id=red.id)
        pla_blue = make_product(item_type="material", color_id=blue.id)
        pla_green = make_product(item_type="material", color_id=green.id)
        _spool(db, pla_red, 800, "Elegoo")
        _spool(db, pla_red, 200, "elegoo")
        _spool(db, pla_red, 500, "Bambu Lab")
        _spool(db, pla_blue, 0, "Elegoo")  # vacía
        _spool(db, pla_green, 900, "Elegoo", status="consumed")
        db.commit()

        colors = _mine(client.get("/api/v1/items/nebula/shop-catalog").json()["colors"], pla_red, pla_blue, pla_green)
        assert list(colors) == [pla_red.id]
        assert colors[pla_red.id]["name"] == "Red"
        assert colors[pla_red.id]["remaining_g"] == 1500.0
        assert colors[pla_red.id]["brands"] == ["Bambu Lab", "Elegoo", "elegoo"]

        # Nombre en la tienda y ocultar
        res = client.put(f"/api/v1/items/nebula/shop-colors/{red.id}", json={"shop_name": "  Rojo  ", "hidden": False})
        assert res.status_code == 200, res.text
        assert res.json()["shop_name"] == "Rojo"
        catalog = client.get("/api/v1/items/nebula/shop-catalog").json()
        assert _mine(catalog["colors"], pla_red)[pla_red.id]["name"] == "Rojo"

        assert client.put(f"/api/v1/items/nebula/shop-colors/{red.id}", json={"shop_name": "Rojo", "hidden": True}).status_code == 200
        assert _mine(client.get("/api/v1/items/nebula/shop-catalog").json()["colors"], pla_red) == {}
        listed = _mine(client.get("/api/v1/items/nebula/shop-colors").json()["colors"], pla_red)
        assert listed[pla_red.id]["hidden"] is True

        assert client.put("/api/v1/items/nebula/shop-colors/999999", json={"hidden": True}).status_code == 404


class TestShopCustomization:
    def test_set_customization(self, client, db, make_product):
        head, size = make_product(), make_product()
        db.commit()
        assert client.put(f"/api/v1/items/{head.id}/shop-sizes", json={"sizes": [{"product_id": size.id, "size_label": "M"}]}).status_code == 200

        res = client.put(f"/api/v1/items/{head.id}/shop-customization", json={"customization": "describe"})
        assert res.status_code == 200, res.text
        assert res.json()["customization"] == "describe"
        catalog = client.get("/api/v1/items/nebula/shop-catalog").json()
        assert catalog["options"][str(head.id)]["customization"] == "describe"
        assert catalog["options"][str(size.id)]["customization"] == "none"

        assert client.put(f"/api/v1/items/{head.id}/shop-customization", json={"customization": "rainbow"}).status_code == 422
        # Un tamaño usa la de su producto
        assert client.put(f"/api/v1/items/{size.id}/shop-customization", json={"customization": "color"}).status_code == 400
        assert client.put(f"/api/v1/items/{size.id}/shop-customization", json={"customization": "none"}).status_code == 200
