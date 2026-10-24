"""PrintFlow: estado en vivo de las impresoras.

Rutas bajo /api/v1/printers (se registran antes que las de FilaOps para que
/printers/nebula/... no choque con /printers/{printer_id}).
"""
import re
from typing import Dict, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_staff_user
from app.db.session import get_db
from app.models import Printer
from app.models.nebula_product import ProductFile
from app.models.product import Product
from app.models.production_order import ProductionOrder
from app.models.user import User
from app.api.v1.endpoints.printers import register_brand
from app.schemas.printer import PrinterBrandInfo, PrinterModelInfo
from app.services.nebula_printer_live import LIVE_BRANDS, MOONRAKER_BRANDS, service
from app.services.printer_discovery.adapters.klipper import KlipperAdapter

router = APIRouter()

# Creality y Klipper: en FilaOps vienen con PRO; en PrintFlow se leen por Moonraker
_klipper = KlipperAdapter()
_CREALITY_MODELS = ["Ender-3 V3", "Ender-3 V3 KE", "Ender-3 V3 Plus", "K1", "K1C", "K1 SE", "K1 Max", "K2 Plus", "Hi"]
register_brand(PrinterBrandInfo(
    code="creality",
    name="Creality",
    supports_discovery=False,
    models=[PrinterModelInfo(value=m, label=f"Creality {m}") for m in _CREALITY_MODELS],
    connection_fields=_klipper.get_connection_fields(),
))
register_brand(PrinterBrandInfo(
    code="klipper",
    name=_klipper.brand_name,
    supports_discovery=False,
    models=[PrinterModelInfo(value=m["value"], label=m["label"]) for m in _klipper.get_supported_models()],
    connection_fields=_klipper.get_connection_fields(),
))

OPEN_ORDER_STATUSES = ("released", "scheduled", "in_progress")


def _stem(name: str) -> str:
    """"Nazareno 20cm.gcode.3mf" / "Nazareno 20cm_plate_1" → "nazareno 20cm"."""
    name = name.strip().lower()
    name = re.sub(r"(\.gcode)?(\.3mf)?$|\.gcode$", "", name)
    name = re.sub(r"[_ -]*plate[_ -]*\d+$", "", name)
    return re.sub(r"[\s_-]+", " ", name).strip()


def _match_product(db: Session, file_name: Optional[str]) -> Optional[Dict]:
    """El artículo que se está imprimiendo: por su 3MF subido o por su nombre."""
    if not file_name:
        return None
    stem = _stem(file_name)
    if not stem:
        return None
    product = None
    for f in db.query(ProductFile).all():
        if _stem(f.original_file_name) == stem:
            product = db.get(Product, f.product_id)
            break
    if product is None:
        for p in db.query(Product).filter(Product.active.is_(True)).all():
            if _stem(p.name or "") == stem:
                product = p
                break
    if product is None:
        return None
    orders = (
        db.query(ProductionOrder)
        .filter(ProductionOrder.product_id == product.id, ProductionOrder.status.in_(OPEN_ORDER_STATUSES))
        .order_by(ProductionOrder.id)
        .all()
    )
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "production_orders": [{"id": o.id, "code": o.code, "status": o.status} for o in orders],
    }


@router.get("/nebula/live")
def printers_live(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    live = service.live()
    printers = (
        db.query(Printer)
        .filter(Printer.active.is_(True), Printer.brand.in_(LIVE_BRANDS))
        .order_by(Printer.code)
        .all()
    )
    result = []
    for printer in printers:
        summary = live.get(printer.id)
        config = printer.connection_config or {}
        required = [("ip_address", config.get("ip_address") or printer.ip_address)]
        if printer.brand not in MOONRAKER_BRANDS:
            required += [
                ("serial_number", config.get("serial") or printer.serial_number),
                ("access_code", config.get("access_code") or config.get("mqtt_access_code")),
            ]
        missing = [field for field, value in required if not value]
        item = {
            "id": printer.id,
            "code": printer.code,
            "name": printer.name,
            "model": printer.model,
            "missing": missing,
            "live": summary,
            "product": None,
        }
        if summary and summary["status"] in ("printing", "paused"):
            item["product"] = _match_product(db, summary.get("file"))
        result.append(item)
    return {"running": service.running, "printers": result}
