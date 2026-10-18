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


class TestBedPricing:
    """Nazareno: 4 por cama; por pieza 39 (sola), 30 (2), 27 (3), 25 (cama llena)."""

    def _nazareno(self, db, make_product):
        product = make_product(selling_price=Decimal("39"), units_per_bed=4)
        replace_tiers(db, product, _tiers(product, (2, "30"), (3, "27"), (4, "25")))
        return product

    def test_breakdown_by_beds(self, db, make_product):
        from app.services.nebula_pricing import price_breakdown

        product = self._nazareno(db, make_product)
        total = lambda q: sum(p["quantity"] * p["unit_price"] for p in price_breakdown(db, product, q))
        assert total(1) == Decimal("39")
        assert total(2) == Decimal("60")
        assert total(3) == Decimal("81")
        assert total(4) == Decimal("100")
        assert total(5) == Decimal("139")   # 4×25 + 1×39
        assert total(7) == Decimal("181")   # 4×25 + 3×27
        assert total(8) == Decimal("200")
        assert total(10) == Decimal("260")  # 8×25 + 2×30
        assert price_for_quantity(db, product, 5) == Decimal("27.8")

    def test_order_splits_lines_by_bed(self, db, make_product):
        product = self._nazareno(db, make_product)
        order = sales_order_service.create_sales_order(
            db, customer_id=None, lines=[{"product_id": product.id, "quantity": 7}],
            created_by_user_id=1,
        )
        lines = (
            db.query(SalesOrderLine).filter_by(sales_order_id=order.id)
            .order_by(SalesOrderLine.id).all()
        )
        assert [(l.quantity, l.unit_price, l.notes) for l in lines] == [
            (Decimal("4"), Decimal("25"), "1 cama completa (4 por cama)"),
            (Decimal("3"), Decimal("27"), "1 cama con 3"),
        ]
        assert order.total_price == Decimal("181.00")

    def test_full_beds_only_is_one_line(self, db, make_product):
        product = self._nazareno(db, make_product)
        order = sales_order_service.create_sales_order(
            db, customer_id=None, lines=[{"product_id": product.id, "quantity": 8}],
            created_by_user_id=1,
        )
        lines = db.query(SalesOrderLine).filter_by(sales_order_id=order.id).all()
        assert len(lines) == 1
        assert lines[0].notes == "2 camas completas (4 por cama)"
        assert order.total_price == Decimal("200.00")

    def test_endpoints(self, client, db, make_product):
        product = make_product(selling_price=Decimal("39"))
        res = client.put(
            f"/api/v1/items/{product.id}/price-tiers",
            json={"units_per_bed": 4, "tiers": [
                {"min_quantity": 2, "unit_price": 30}, {"min_quantity": 3, "unit_price": 27},
                {"min_quantity": 4, "unit_price": 25}]},
        )
        assert res.status_code == 200, res.text
        assert res.json()["units_per_bed"] == 4

        res = client.get(f"/api/v1/items/{product.id}/price", params={"quantity": 5})
        assert res.json()["total"] == 139
        assert [p["quantity"] for p in res.json()["parts"]] == [4, 1]

        pricing = client.get("/api/v1/items/nebula/pricing", params={"ids": str(product.id)}).json()
        assert pricing[str(product.id)]["units_per_bed"] == 4
        assert len(pricing[str(product.id)]["tiers"]) == 3

        # Sin enviar units_per_bed se mantiene; con null se quita
        client.put(f"/api/v1/items/{product.id}/price-tiers", json={"tiers": []})
        db.refresh(product)
        assert product.units_per_bed == 4
        client.put(f"/api/v1/items/{product.id}/price-tiers", json={"tiers": [], "units_per_bed": None})
        db.refresh(product)
        assert product.units_per_bed is None

    def test_import_per_bed(self, db):
        csv = (
            "sku;nombre;precio;piezas_por_cama;precio_desde_2;precio_desde_3;precio_desde_4\n"
            "NAZ-CAMA-1;Nazareno;39;4;30;27;25\n"
        ).encode()
        result = nebula_import.import_items(db, csv)
        assert result["created"] == 1, result
        product = db.query(Product).filter_by(sku="NAZ-CAMA-1").one()
        assert product.units_per_bed == 4
        assert price_for_quantity(db, product, 4) == Decimal("25")
