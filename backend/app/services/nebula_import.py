"""PrintFlow: importar artículos desde un CSV en español (o el de Excel).

Prepara el fichero para el importador de FilaOps (``import_items_from_csv``):

- acepta separador ``;`` (Excel en español), ``,`` o tabulador;
- entiende cabeceras en español (nombre, precio, coste, categoría, tipo…);
- pasa los números con coma decimal ("3,50") a punto, que el importador de
  FilaOps quitaría la coma y leería 350;
- lee los precios por cantidad: columnas ``precio_desde_4``, ``precio_200``… o
  una columna ``tramos`` con ``4=3,50 | 200=1,20``;
- lee ``piezas_por_cama``: con ella los tramos son el precio por pieza según
  cuántas van en la cama (ver nebula_pricing).

Los tramos se aplican a los artículos creados y, si se marca "actualizar los
que ya existen", también a esos (sustituyen a los que tuvieran).
"""
import csv
import io
import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.item_import_service import import_items_from_csv
from app.services.nebula_pricing import replace_tiers

_HEADERS = {
    "sku": "sku", "referencia": "sku", "ref": "sku", "codigo": "sku",
    "nombre": "name", "name": "name", "titulo": "name", "title": "name", "producto": "name",
    "descripcion": "description", "description": "description",
    "precio": "price", "price": "price", "pvp": "price", "precio_venta": "price",
    "precio_de_venta": "price", "selling_price": "price",
    "coste": "cost", "costo": "cost", "cost": "cost", "precio_coste": "cost",
    "precio_de_coste": "cost", "standard_cost": "cost",
    "categoria": "Category", "category": "Category",
    "tipo": "item_type", "type": "item_type", "item_type": "item_type",
    "unidad": "unit", "unit": "unit",
    "ean": "upc", "upc": "upc", "codigo_barras": "upc", "codigo_de_barras": "upc",
    "punto_pedido": "reorder_point", "punto_de_pedido": "reorder_point",
    "reorder_point": "reorder_point",
    "tramos": "_tiers", "precios_por_cantidad": "_tiers", "price_tiers": "_tiers",
    "piezas_por_cama": "_per_bed", "piezas_cama": "_per_bed", "por_cama": "_per_bed",
    "units_per_bed": "_per_bed",
}
_NUMERIC = {"price", "cost", "reorder_point"}
_TIER_HEADER = re.compile(r"^(?:precio|price|pvp)_(?:desde_|de_|x_?|a_partir_de_)?(\d+)(?:_(?:uds?|unidades|mas))?$")

_TYPES = {
    "producto": "finished_good", "producto_terminado": "finished_good", "terminado": "finished_good",
    "componente": "component", "pieza": "component",
    "embalaje": "packaging", "envase": "packaging", "caja": "packaging",
    "consumible": "supply", "suministro": "supply",
    "servicio": "service",
    "material": "material", "filamento": "material", "materia_prima": "material",
}

_ERRORS = {
    "SKU is required": "Falta el SKU",
    "Name is required": "Falta el nombre",
}

TEMPLATE_HEADERS = [
    "sku", "nombre", "descripcion", "tipo", "categoria", "precio", "coste",
    "piezas_por_cama", "precio_desde_2", "precio_desde_3", "precio_desde_4", "precio_desde_200",
]
# Nazareno: 4 por cama, precio por pieza según cuántas van en la cama.
# Llavero: sin camas, más barato a partir de 200 unidades.
TEMPLATE_ROWS = [
    ["NAZ-001", "Nazareno 35 cm", "Nazareno porta medallas", "producto",
     "Semana Santa", "39,00", "8,00", "4", "30,00", "27,00", "25,00", ""],
    ["LLA-001", "Llavero escudo", "Llavero pequeño", "producto", "Llaveros", "2,50", "0,30",
     "", "", "", "", "0,90"],
]


def _key(header: str) -> str:
    text = unicodedata.normalize("NFKD", header or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def normalize_number(value: str) -> str:
    """"1.234,50 €" → "1234.50"; "3,5" → "3.5"; vacío → vacío."""
    text = re.sub(r"[^\d,.\-]", "", value or "")
    if not text:
        return ""
    if "," in text and "." in text:
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        text = text.replace(thousands, "").replace(decimal, ".")
    else:
        text = text.replace(",", ".")
    return text


def parse_tiers(text: str) -> list[dict]:
    """"4=3,50 | 200=1,20" → [{min_quantity: "4", unit_price: "3.50"}, …]"""
    tiers = []
    for part in re.split(r"[|;\n]+", text or ""):
        if not part.strip():
            continue
        match = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*(?:uds?|unidades)?\s*[=:]\s*(.+?)\s*$", part)
        if not match:
            raise ValueError(f"tramo no válido: {part.strip()!r} (formato: 4=3,50)")
        tiers.append({
            "min_quantity": normalize_number(match.group(1)),
            "unit_price": normalize_number(match.group(2)),
        })
    return tiers


def _decode(content: bytes) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("cp1252", errors="replace")
    return text[1:] if text.startswith("﻿") else text


def _delimiter(text: str) -> str:
    first = text.split("\n", 1)[0]
    return max([";", ",", "\t"], key=first.count)


def template_csv() -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerows(TEMPLATE_ROWS)
    # BOM para que Excel lo abra en UTF-8 (tildes y €)
    return ("﻿" + out.getvalue()).encode("utf-8")


def import_items(
    db: Session,
    content: bytes,
    *,
    update_existing: bool = False,
    default_item_type: str = "finished_good",
    default_category_id: int | None = None,
) -> dict:
    text = _decode(content)
    reader = csv.reader(io.StringIO(text), delimiter=_delimiter(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return {"total_rows": 0, "created": 0, "updated": 0, "skipped": 0,
                "errors": [{"row": 1, "error": "El fichero está vacío"}], "warnings": [],
                "tiers_updated": 0}

    header = rows[0]
    columns = []  # (destino, cantidad del tramo o None)
    for raw in header:
        key = _key(raw)
        tier = _TIER_HEADER.match(key)
        if tier:
            columns.append(("_tier", int(tier.group(1))))
        else:
            columns.append((_HEADERS.get(key, raw.strip()), None))

    out_header = []
    for name, qty in columns:
        if name not in ("_tier", "_tiers") and name not in out_header:
            out_header.append(name)

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=out_header, extrasaction="ignore")
    writer.writeheader()

    tier_rows: dict[str, list[dict]] = {}
    bed_rows: dict[str, int | None] = {}
    errors: list[dict] = []
    for row_num, row in enumerate(rows[1:], start=2):
        record: dict[str, str] = {}
        tiers: list[dict] = []
        per_bed: str | None = None
        try:
            for (name, qty), cell in zip(columns, row):
                cell = cell.strip()
                if name == "_tier":
                    if cell:
                        tiers.append({"min_quantity": str(qty), "unit_price": normalize_number(cell)})
                elif name == "_tiers":
                    tiers.extend(parse_tiers(cell))
                elif name == "_per_bed":
                    per_bed = cell
                elif name in _NUMERIC:
                    record.setdefault(name, normalize_number(cell))
                elif name == "item_type":
                    record.setdefault(name, _TYPES.get(_key(cell), cell))
                elif name == "sku":
                    record.setdefault(name, cell.upper())
                else:
                    record.setdefault(name, cell)
        except ValueError as exc:
            errors.append({"row": row_num, "sku": record.get("sku", ""), "error": str(exc)})
            # La fila entra igual, sin tramos
            tiers = []
        writer.writerow(record)
        if tiers and record.get("sku"):
            tier_rows[record["sku"]] = tiers
        if per_bed and record.get("sku"):
            try:
                value = int(float(normalize_number(per_bed)))
                if value < 1:
                    raise ValueError
                bed_rows[record["sku"]] = value
            except ValueError:
                errors.append({"row": row_num, "sku": record["sku"],
                               "error": f"piezas por cama no válidas: {per_bed!r}"})

    touched = set(tier_rows) | set(bed_rows)
    existing = {
        sku for (sku,) in db.query(Product.sku).filter(Product.sku.in_(list(touched))).all()
    } if touched else set()

    result = import_items_from_csv(
        db,
        file_content=out.getvalue().encode("utf-8"),
        update_existing=update_existing,
        default_item_type=default_item_type,
        default_category_id=default_category_id,
    )
    for err in result["errors"]:
        err["error"] = _ERRORS.get(err.get("error"), err.get("error"))
    result["errors"] = errors + result["errors"]

    tiers_updated = 0
    for sku, tiers in tier_rows.items():
        if sku in existing and not update_existing:
            continue
        product = db.query(Product).filter(Product.sku == sku).first()
        if product is None:
            continue
        try:
            with db.begin_nested():
                replace_tiers(db, product, tiers)
            tiers_updated += 1
        except Exception as exc:  # HTTPException con el motivo
            detail = getattr(exc, "detail", str(exc))
            result["errors"].append({"sku": sku, "error": f"Precios por cantidad: {detail}"})
    for sku, value in bed_rows.items():
        if sku in existing and not update_existing:
            continue
        product = db.query(Product).filter(Product.sku == sku).first()
        if product is not None:
            product.units_per_bed = value
    db.commit()
    result["tiers_updated"] = tiers_updated
    return result
