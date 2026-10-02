"""PrintFlow: idioma del PDF de la factura (endpoint y descarga)."""
from decimal import Decimal

from app.services.invoice_service import create_invoice


def _invoice(db, make_product, make_sales_order):
    product = make_product(selling_price=Decimal("25.00"))
    so = make_sales_order(product_id=product.id, quantity=2, unit_price=Decimal("25.00"), status="confirmed")
    return create_invoice(db, so.id)


def test_cambiar_idioma_de_la_factura(client, db, make_product, make_sales_order):
    inv = _invoice(db, make_product, make_sales_order)
    assert client.get(f"/api/v1/invoices/{inv.id}").json()["language"] is None

    r = client.put(f"/api/v1/invoices/{inv.id}/language", json={"language": "en"})
    assert r.status_code == 200, r.text
    assert r.json()["language"] == "en"
    # no toca importes ni estado
    assert Decimal(str(r.json()["total"])) == Decimal("50.00")
    assert r.json()["status"] == "draft"


def test_idioma_no_admitido(client, db, make_product, make_sales_order):
    inv = _invoice(db, make_product, make_sales_order)
    r = client.put(f"/api/v1/invoices/{inv.id}/language", json={"language": "fr"})
    assert r.status_code == 422


def test_descargar_pdf_en_cada_idioma(client, db, make_product, make_sales_order):
    inv = _invoice(db, make_product, make_sales_order)
    for lang in ("es", "en", None):
        url = f"/api/v1/invoices/{inv.id}/pdf" + (f"?lang={lang}" if lang else "")
        r = client.get(url)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
    assert client.get(f"/api/v1/invoices/{inv.id}/pdf?lang=fr").status_code == 422


def test_pdf_cambia_segun_idioma(db, make_product, make_sales_order):
    """El contenido es distinto en español y en inglés (los textos van comprimidos,
    así que se compara el tamaño/bytes en lugar de buscar palabras)."""
    from app.services.invoice_service import generate_invoice_pdf

    inv = _invoice(db, make_product, make_sales_order)
    es = generate_invoice_pdf(db, inv.id, language="es").getvalue()
    en = generate_invoice_pdf(db, inv.id, language="en").getvalue()
    assert es.startswith(b"%PDF") and en.startswith(b"%PDF")
    assert es != en
