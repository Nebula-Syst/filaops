"""PrintFlow: precios por cantidad, archivos 3MF e importación en español."""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.nebula_product import ProductFile, ProductPriceTier
from app.models.product import Product
from app.models.sales_order import SalesOrderLine
from app.services import nebula_import, sales_order_service
from app.services.nebula_pricing import price_for_quantity, replace_tiers


def _tiers(product, *pairs):
    return [{"min_quantity": q, "unit_price": p} for q, p in pairs]


class TestPriceTiers:
    def test_price_depends_on_quantity(self, db, make_product):
        product = make_product(selling_price=Decimal("6"))
        replace_tiers(db, product, _tiers(product, (4, "4.5"), (200, "2")))

        assert price_for_quantity(db, product, 1) == Decimal("6")
        assert price_for_quantity(db, product, 3) == Decimal("6")
        assert price_for_quantity(db, product, 4) == Decimal("4.5")
        assert price_for_quantity(db, product, 199) == Decimal("4.5")
        assert price_for_quantity(db, product, 200) == Decimal("2")
        assert price_for_quantity(db, product, 1000) == Decimal("2")

    def test_replace_overwrites_and_validates(self, db, make_product):
        product = make_product(selling_price=Decimal("6"))
        replace_tiers(db, product, _tiers(product, (4, "4.5"), (10, "4")))
        replace_tiers(db, product, _tiers(product, (20, "3,5")))
        rows = db.query(ProductPriceTier).filter_by(product_id=product.id).all()
        assert [(r.min_quantity, r.unit_price) for r in rows] == [(Decimal("20"), Decimal("3.5"))]

        with pytest.raises(HTTPException):
            replace_tiers(db, product, _tiers(product, (4, "1"), (4, "2")))
        with pytest.raises(HTTPException):
            replace_tiers(db, product, _tiers(product, (0, "1")))

    def test_sales_order_uses_tier_price(self, db, make_product):
        product = make_product(selling_price=Decimal("6"))
        replace_tiers(db, product, _tiers(product, (4, "4.5")))

        order = sales_order_service.create_sales_order(
            db, customer_id=None, lines=[{"product_id": product.id, "quantity": 4}],
            created_by_user_id=1,
        )
        line = db.query(SalesOrderLine).filter_by(sales_order_id=order.id).one()
        assert line.unit_price == Decimal("4.5")
        assert order.total_price == Decimal("18.00")

        # Un precio puesto a mano manda sobre el tramo
        order = sales_order_service.create_sales_order(
            db, customer_id=None,
            lines=[{"product_id": product.id, "quantity": 4, "unit_price": Decimal("5")}],
            created_by_user_id=1,
        )
        line = db.query(SalesOrderLine).filter_by(sales_order_id=order.id).one()
        assert line.unit_price == Decimal("5")

    def test_endpoints(self, client, db, make_product):
        product = make_product(selling_price=Decimal("6"))
        res = client.put(
            f"/api/v1/items/{product.id}/price-tiers",
            json={"tiers": [{"min_quantity": 200, "unit_price": 2}, {"min_quantity": 4, "unit_price": 4.5, "label": "4 por cama"}]},
        )
        assert res.status_code == 200, res.text
        assert [t["min_quantity"] for t in res.json()["tiers"]] == [4, 200]

        res = client.get(f"/api/v1/items/{product.id}/price", params={"quantity": 5})
        assert res.json()["unit_price"] == 4.5

        res = client.get("/api/v1/items/nebula/price-tiers", params={"ids": str(product.id)})
        assert res.status_code == 200
        assert res.json()[str(product.id)][0]["label"] == "4 por cama"


class TestProductFiles:
    def test_upload_download_delete(self, client, db, make_product, tmp_path, monkeypatch):
        from app.api.v1.endpoints import nebula_items
        monkeypatch.setattr(nebula_items, "FILES_DIR", tmp_path)
        product = make_product()

        res = client.post(
            f"/api/v1/items/{product.id}/files",
            files=[
                ("files", ("placa 1.3mf", b"PK-uno", "application/octet-stream")),
                ("files", ("placa 2.3mf", b"PK-dos", "application/octet-stream")),
            ],
        )
        assert res.status_code == 201, res.text
        uploaded = res.json()
        assert [f["file_name"] for f in uploaded] == ["placa 1.3mf", "placa 2.3mf"]
        assert len(list(tmp_path.iterdir())) == 2

        listed = client.get(f"/api/v1/items/{product.id}/files").json()
        assert len(listed) == 2

        res = client.get(uploaded[1]["download_url"])
        assert res.status_code == 200
        assert res.content == b"PK-dos"
        assert "placa%202.3mf" in res.headers["content-disposition"] or "placa 2.3mf" in res.headers["content-disposition"]

        res = client.patch(f"/api/v1/items/{product.id}/files/{uploaded[0]['id']}", json={"notes": "PLA blanco"})
        assert res.json()["notes"] == "PLA blanco"

        assert client.delete(f"/api/v1/items/{product.id}/files/{uploaded[0]['id']}").status_code == 200
        assert len(list(tmp_path.iterdir())) == 1
        assert db.query(ProductFile).filter_by(product_id=product.id).count() == 1

        # Otro artículo no puede bajar este archivo
        other = make_product()
        assert client.get(f"/api/v1/items/{other.id}/files/{uploaded[1]['id']}/download").status_code == 404

    def test_rejects_unknown_extension(self, client, make_product, tmp_path, monkeypatch):
        from app.api.v1.endpoints import nebula_items
        monkeypatch.setattr(nebula_items, "FILES_DIR", tmp_path)
        product = make_product()
        res = client.post(
            f"/api/v1/items/{product.id}/files",
            files=[("files", ("virus.exe", b"MZ", "application/octet-stream"))],
        )
        assert res.status_code == 400
        assert list(tmp_path.iterdir()) == []


class TestSpanishImport:
    CSV = (
        "﻿SKU;Nombre;Descripción;Tipo;Precio;Coste;Precio desde 4;precio_200;tramos\n"
        "naz-imp-1;Nazareno;Figura;producto;6,00 €;1,20;4,50;;\n"
        "LLA-IMP-1;Llavero;;producto;2,5;0,3;;0,90;10=2\n"
        ";Sin SKU;;;1;;;;\n"
    ).encode("utf-8")

    def test_import_with_tiers(self, db):
        result = nebula_import.import_items(db, self.CSV)
        assert result["created"] == 2
        assert result["skipped"] == 1
        assert result["errors"][0]["error"] == "Falta el SKU"
        assert result["tiers_updated"] == 2

        naz = db.query(Product).filter_by(sku="NAZ-IMP-1").one()
        assert naz.selling_price == Decimal("6")
        assert naz.standard_cost == Decimal("1.2")
        assert naz.description == "Figura"
        assert naz.item_type == "finished_good"
        assert price_for_quantity(db, naz, 4) == Decimal("4.5")

        lla = db.query(Product).filter_by(sku="LLA-IMP-1").one()
        assert lla.selling_price == Decimal("2.5")
        assert price_for_quantity(db, lla, 10) == Decimal("2")
        assert price_for_quantity(db, lla, 200) == Decimal("0.9")

    def test_existing_items_untouched_unless_update(self, db, make_product):
        product = make_product(sku="NAZ-IMP-1", selling_price=Decimal("9"))
        nebula_import.import_items(db, self.CSV)
        db.refresh(product)
        assert product.selling_price == Decimal("9")
        assert price_for_quantity(db, product, 4) == Decimal("9")

        nebula_import.import_items(db, self.CSV, update_existing=True)
        db.refresh(product)
        assert product.selling_price == Decimal("6")
        assert price_for_quantity(db, product, 4) == Decimal("4.5")

    def test_numbers_and_template(self):
        assert nebula_import.normalize_number("1.234,50 €") == "1234.50"
        assert nebula_import.normalize_number("1,234.50") == "1234.50"
        assert nebula_import.normalize_number("3,5") == "3.5"
        assert nebula_import.normalize_number("") == ""
        assert nebula_import.parse_tiers("4=3,50 | 200 uds: 1,2") == [
            {"min_quantity": "4", "unit_price": "3.50"},
            {"min_quantity": "200", "unit_price": "1.2"},
        ]
        assert nebula_import.template_csv().decode("utf-8").startswith("﻿sku;nombre")

    def test_import_endpoint(self, client):
        res = client.get("/api/v1/items/nebula/import-template")
        assert res.status_code == 200
        res = client.post(
            "/api/v1/items/nebula/import",
            files={"file": ("articulos.csv", self.CSV, "text/csv")},
        )
        assert res.status_code == 200, res.text
        assert res.json()["created"] == 2
