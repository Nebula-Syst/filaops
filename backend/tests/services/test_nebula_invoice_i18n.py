"""PrintFlow: idioma del PDF de factura."""
from datetime import date, datetime
from types import SimpleNamespace

from app.services import nebula_invoice_i18n as i18n


def test_idioma_por_defecto_segun_empresa():
    assert i18n.resolve_language(None, None, SimpleNamespace(locale="es-ES")) == "es"
    assert i18n.resolve_language(None, None, SimpleNamespace(locale="en-US")) == "en"
    assert i18n.resolve_language(None, None, None) == "en"


def test_idioma_de_la_factura_y_explicito_mandan():
    es_company = SimpleNamespace(locale="es-ES")
    assert i18n.resolve_language(None, SimpleNamespace(language="en"), es_company) == "en"
    assert i18n.resolve_language("es", SimpleNamespace(language="en"), es_company) == "es"
    assert i18n.resolve_language("fr", SimpleNamespace(language=None), es_company) == "es"


def test_fechas():
    assert i18n.fmt_date(date(2026, 10, 2), "es") == "2 de octubre de 2026"
    assert i18n.fmt_date(datetime(2026, 10, 2, 9, 30), "en") == "October 02, 2026"
    assert i18n.fmt_date(None, "es") == "—"


def test_importes():
    assert i18n.fmt_money("1234.5", "€", "EUR", "es") == "1.234,50 €"
    assert i18n.fmt_money("1234.5", "€", "EUR", "en") == "€1,234.50"
    assert i18n.fmt_money("25", "$", "USD", "es") == "25,00 $"


def test_condiciones():
    assert i18n.terms_name("cod", "es") == "Contra reembolso"
    assert i18n.terms_name("net30", "en") == "NET 30"
    assert "15 días" in i18n.terms_verbiage("net_15", date(2026, 10, 17), "es")
    assert "17 de octubre de 2026" in i18n.terms_verbiage("net_15", date(2026, 10, 17), "es")
    assert i18n.terms_verbiage("cod", None, "en").startswith("Payment is due upon delivery")
