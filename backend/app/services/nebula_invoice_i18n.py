"""PrintFlow: textos del PDF de factura en español e inglés.

Cada factura guarda su idioma (invoices.language). Si no tiene, se usa el de la
empresa (company_settings.locale: "es-*" → español; cualquier otro → inglés).
El texto personalizado de la empresa (condiciones, pie) se imprime tal cual.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

SUPPORTED = ("es", "en")

_MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

LABELS = {
    "en": {
        "invoice": "INVOICE",
        "date": "Date",
        "due": "Due",
        "terms": "Terms",
        "order": "Order",
        "bill_to": "BILL TO",
        "sku": "SKU",
        "description": "DESCRIPTION",
        "qty": "QTY",
        "unit_price": "UNIT PRICE",
        "amount": "AMOUNT",
        "subtotal": "Subtotal",
        "discount": "Discount",
        "sales_tax": "Sales Tax",
        "shipping": "Shipping",
        "total_due": "Total Due",
        "amount_paid": "Amount Paid",
        "balance_due": "Balance Due",
        "payment_terms": "PAYMENT TERMS",
        "thank_you": (
            "Thank you for your business with {company}. "
            "Questions? Please contact us and reference your invoice number."
        ),
        "us": "us",
        "due_date_fallback": "the due date shown above",
    },
    "es": {
        "invoice": "FACTURA",
        "date": "Fecha",
        "due": "Vencimiento",
        "terms": "Condiciones",
        "order": "Pedido",
        "bill_to": "FACTURAR A",
        "sku": "REF.",
        "description": "DESCRIPCIÓN",
        "qty": "CANT.",
        "unit_price": "PRECIO UNIT.",
        "amount": "IMPORTE",
        "subtotal": "Subtotal",
        "discount": "Descuento",
        "sales_tax": "Impuestos",
        "shipping": "Envío",
        "total_due": "Total a pagar",
        "amount_paid": "Pagado",
        "balance_due": "Pendiente de pago",
        "payment_terms": "CONDICIONES DE PAGO",
        "thank_you": (
            "Gracias por confiar en {company}. "
            "Si tienes cualquier duda, contacta con nosotros indicando el número de factura."
        ),
        "us": "nosotros",
        "due_date_fallback": "la fecha de vencimiento indicada arriba",
    },
}

# Nombre corto de las condiciones de pago (cabecera "Condiciones: …")
TERMS_NAMES = {
    "en": {"cod": "COD", "prepaid": "PREPAID", "net_15": "NET 15", "net_30": "NET 30",
           "net_60": "NET 60", "card_on_file": "CARD ON FILE"},
    "es": {"cod": "Contra reembolso", "prepaid": "Pago por adelantado", "net_15": "15 días",
           "net_30": "30 días", "net_60": "60 días", "card_on_file": "Tarjeta guardada"},
}

_TERMS_ALIASES = {"prepay": "prepaid", "net15": "net_15", "net30": "net_30", "net60": "net_60"}


def resolve_language(requested: Optional[str], invoice=None, settings=None) -> str:
    """Idioma del PDF: el pedido explícitamente > el de la factura > el de la empresa."""
    for candidate in (requested, getattr(invoice, "language", None)):
        if candidate and candidate.lower()[:2] in SUPPORTED:
            return candidate.lower()[:2]
    locale = (getattr(settings, "locale", None) or "").lower()
    return "es" if locale.startswith("es") else "en"


def normalize_terms(code: Optional[str]) -> str:
    key = (code or "").strip().lower().replace(" ", "_").replace("-", "_")
    return _TERMS_ALIASES.get(key, key)


def terms_name(code: Optional[str], lang: str) -> str:
    key = normalize_terms(code)
    return TERMS_NAMES[lang].get(key) or (code or "").upper()


def fmt_date(value, lang: str) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        return str(value)
    if lang == "es":
        return f"{value.day} de {_MONTHS_ES[value.month - 1]} de {value.year}"
    return value.strftime("%B %d, %Y")


def fmt_money(amount, symbol: str, currency: str, lang: str) -> str:
    value = Decimal(str(amount or "0")).quantize(Decimal("0.01"))
    text = f"{value:,.2f}"
    if lang == "es":
        # 1,234.56 → 1.234,56 y el símbolo detrás (uso habitual en España)
        text = text.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
        sym = symbol.strip().replace(" ", "") or currency
        return f"{text} {sym}"
    return f"{symbol}{text}"


def terms_verbiage(code: Optional[str], due_date, lang: str) -> str:
    """Texto de condiciones de pago (el mismo contenido que upstream, traducido)."""
    key = normalize_terms(code)
    due = fmt_date(due_date, lang) if due_date else LABELS[lang]["due_date_fallback"]
    if lang == "es":
        texts = {
            "cod": "El pago se realiza a la entrega. Ten el importe preparado cuando llegue tu pedido.",
            "prepaid": "El pago se realiza antes del envío. La producción empieza al confirmarse el pago.",
            "net_15": f"El pago vence a los 15 días de la fecha de factura. Realiza el pago antes del {due}.",
            "net_30": f"El pago vence a los 30 días de la fecha de factura. Realiza el pago antes del {due}.",
            "net_60": f"El pago vence a los 60 días de la fecha de factura. Realiza el pago antes del {due}.",
        }
        return texts.get(key) or f"El pago vence el {due}."
    texts = {
        "cod": ("Payment is due upon delivery. Please ensure payment is prepared "
                "and ready at the time your order arrives."),
        "prepaid": ("Payment is due prior to shipment. Production will begin upon "
                    "confirmation of payment."),
        "net_15": f"Payment is due within 15 days of the invoice date. Please remit payment by {due}.",
        "net_30": f"Payment is due within 30 days of the invoice date. Please remit payment by {due}.",
        "net_60": f"Payment is due within 60 days of the invoice date. Please remit payment by {due}.",
    }
    return texts.get(key) or f"Payment is due by {due}."
