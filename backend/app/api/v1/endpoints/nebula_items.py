"""PrintFlow: precios por cantidad, archivos 3MF e importación de artículos.

Rutas bajo /api/v1/items (se registran antes que las de FilaOps para que
/items/nebula/... no choque con /items/{item_id}).
"""
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_staff_user
from app.core.paths import BACKEND_DIR
from app.db.session import get_db
from app.logging_config import get_logger
from app.models.nebula_product import ProductFile
from app.models.product import Product
from app.models.user import User
from app.services import nebula_import
from app.services.nebula_pricing import (
    list_tiers, price_for_quantity, replace_tiers, tier_to_dict, tiers_by_product,
)

router = APIRouter()
logger = get_logger(__name__)

FILES_DIR = Path(os.environ.get("UPLOAD_PRODUCT_FILES_DIR") or BACKEND_DIR / "uploads" / "product_files")
ALLOWED_EXTENSIONS = {
    ".3mf", ".stl", ".obj", ".step", ".stp", ".gcode", ".gco", ".bgcode", ".zip", ".pdf",
    ".png", ".jpg", ".jpeg",
}
MAX_FILE_BYTES = 100 * 1024 * 1024  # el túnel de Cloudflare no deja subir más de 100 MB
_CHUNK = 1024 * 1024


def _product(db: Session, item_id: int) -> Product:
    product = db.query(Product).filter(Product.id == item_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    return product


# ---------------------------------------------------------------------------
# Precios por cantidad
# ---------------------------------------------------------------------------


class PriceTierIn(BaseModel):
    min_quantity: float = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)
    label: Optional[str] = Field(None, max_length=100)


class PriceTiersIn(BaseModel):
    tiers: List[PriceTierIn]


@router.get("/nebula/price-tiers")
def all_price_tiers(
    ids: Optional[str] = Query(None, description="IDs separados por comas; vacío = todos"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Tramos de varios artículos: {product_id: [tramos]}."""
    product_ids = None
    if ids:
        try:
            product_ids = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="ids no válidos")
    return {str(k): v for k, v in tiers_by_product(db, product_ids).items()}


@router.get("/{item_id}/price-tiers")
def get_price_tiers(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    product = _product(db, item_id)
    return {
        "base_price": float(product.selling_price) if product.selling_price is not None else None,
        "tiers": [tier_to_dict(t) for t in list_tiers(db, item_id)],
    }


@router.put("/{item_id}/price-tiers")
def put_price_tiers(
    item_id: int,
    body: PriceTiersIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Sustituye todos los tramos del artículo (lista vacía = quitarlos)."""
    product = _product(db, item_id)
    tiers = replace_tiers(db, product, [t.model_dump() for t in body.tiers])
    db.commit()
    return {
        "base_price": float(product.selling_price) if product.selling_price is not None else None,
        "tiers": [tier_to_dict(t) for t in tiers],
    }


@router.get("/{item_id}/price")
def get_price_for_quantity(
    item_id: int,
    quantity: float = Query(1, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    product = _product(db, item_id)
    return {"quantity": quantity, "unit_price": float(price_for_quantity(db, product, quantity))}


# ---------------------------------------------------------------------------
# Archivos de impresión (3MF…)
# ---------------------------------------------------------------------------


def _file_to_dict(f: ProductFile) -> dict:
    return {
        "id": f.id,
        "product_id": f.product_id,
        "file_name": f.original_file_name,
        "file_size": f.file_size,
        "mime_type": f.mime_type,
        "notes": f.notes,
        "uploaded_by": f.uploaded_by,
        "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
        "download_url": f"/api/v1/items/{f.product_id}/files/{f.id}/download",
    }


def _safe_name(name: str) -> str:
    base = os.path.basename(name or "").strip() or "archivo"
    return re.sub(r"[\x00-\x1f/\\]", "_", base)[:255]


@router.get("/{item_id}/files")
def list_files(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    _product(db, item_id)
    files = (
        db.query(ProductFile)
        .filter(ProductFile.product_id == item_id)
        .order_by(ProductFile.uploaded_at, ProductFile.id)
        .all()
    )
    return [_file_to_dict(f) for f in files]


@router.post("/{item_id}/files", status_code=201)
async def upload_files(
    item_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Sube uno o varios archivos al artículo."""
    product = _product(db, item_id)
    for upload in files:
        ext = os.path.splitext(upload.filename or "")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"{upload.filename}: tipo de archivo no admitido "
                f"({', '.join(sorted(ALLOWED_EXTENSIONS))})",
            )

    FILES_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    created: list[ProductFile] = []
    try:
        for upload in files:
            original = _safe_name(upload.filename)
            ext = os.path.splitext(original)[1].lower()
            stored = f"{product.id}_{uuid.uuid4().hex}{ext}"
            target = FILES_DIR / stored
            size = 0
            with open(target, "wb") as out:
                written.append(target)
                while chunk := await upload.read(_CHUNK):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"{original}: pasa de {MAX_FILE_BYTES // (1024 * 1024)} MB",
                        )
                    out.write(chunk)
            record = ProductFile(
                product_id=product.id,
                original_file_name=original,
                stored_file_name=stored,
                file_size=size,
                mime_type=upload.content_type or mimetypes.guess_type(original)[0],
                uploaded_by=current_user.id,
            )
            db.add(record)
            created.append(record)
        db.commit()
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    for record in created:
        db.refresh(record)
    logger.info("Archivos subidos al artículo %s: %s", product.sku, [c.original_file_name for c in created])
    return [_file_to_dict(f) for f in created]


def _get_file(db: Session, item_id: int, file_id: int) -> ProductFile:
    record = (
        db.query(ProductFile)
        .filter(ProductFile.id == file_id, ProductFile.product_id == item_id)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return record


@router.get("/{item_id}/files/{file_id}/download")
def download_file(
    item_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    record = _get_file(db, item_id, file_id)
    path = FILES_DIR / record.stored_file_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="El archivo ya no está en el servidor")
    return FileResponse(
        path,
        filename=record.original_file_name,
        media_type=record.mime_type or "application/octet-stream",
    )


class FileNotesIn(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


@router.patch("/{item_id}/files/{file_id}")
def update_file(
    item_id: int,
    file_id: int,
    body: FileNotesIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    record = _get_file(db, item_id, file_id)
    record.notes = (body.notes or "").strip() or None
    db.commit()
    return _file_to_dict(record)


@router.delete("/{item_id}/files/{file_id}")
def delete_file(
    item_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    record = _get_file(db, item_id, file_id)
    stored = record.stored_file_name
    db.delete(record)
    db.commit()
    (FILES_DIR / stored).unlink(missing_ok=True)
    return {"deleted": file_id}


# ---------------------------------------------------------------------------
# Importar artículos
# ---------------------------------------------------------------------------


@router.get("/nebula/import-template")
def import_template(current_user: User = Depends(get_current_staff_user)):
    return Response(
        content=nebula_import.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plantilla-articulos.csv"'},
    )


@router.post("/nebula/import")
async def import_items(
    file: UploadFile = File(...),
    update_existing: bool = Query(False),
    default_item_type: str = Query("finished_good"),
    default_category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    name = (file.filename or "").lower()
    if not name.endswith((".csv", ".txt")):
        raise HTTPException(
            status_code=400,
            detail="Tiene que ser un CSV. En Excel: Archivo → Guardar como → CSV (delimitado por punto y coma)",
        )
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El CSV pasa de 10 MB")
    return nebula_import.import_items(
        db,
        content,
        update_existing=update_existing,
        default_item_type=default_item_type,
        default_category_id=default_category_id,
    )
