"""PrintFlow: precios por cantidad y archivos de impresión de cada artículo.

- ``ProductPriceTier``: precio unitario a partir de una cantidad. Imprimiendo
  varias piezas por cama sale más barato, así que 4 nazarenos no cuestan 4 veces
  uno. Por debajo del primer tramo se usa ``Product.selling_price``.
- ``ProductFile``: los 3MF (o STL, gcode…) con los que se imprime el artículo;
  puede tener varios si el producto lleva varias placas o piezas.
- ``ProductShopLink``: la ficha del artículo en cada tienda online; la rellena
  la sincronización de las tiendas.
- ``ShopStore`` / ``ProductShopStore``: las tiendas online y qué artículos van
  a cada una (se elige en PrintFlow y la tienda lo obedece).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class ProductPriceTier(Base):
    __tablename__ = "product_price_tiers"
    __table_args__ = (
        UniqueConstraint("product_id", "min_quantity", name="uq_product_price_tiers_qty"),
        CheckConstraint("min_quantity >= 1", name="ck_product_price_tiers_min_qty"),
        CheckConstraint("unit_price >= 0", name="ck_product_price_tiers_price"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    min_quantity = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(18, 4), nullable=False)
    label = Column(String(100), nullable=True)  # p. ej. "4 por cama"

    product = relationship("Product")


class ProductFile(Base):
    __tablename__ = "product_files"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    original_file_name = Column(String(255), nullable=False)
    stored_file_name = Column(String(255), nullable=False, unique=True)
    file_size = Column(BigInteger, nullable=True)
    mime_type = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    product = relationship("Product")


class ProductShopLink(Base):
    __tablename__ = "product_shop_links"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    store = Column(String(200), nullable=False)
    url = Column(String(500), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ShopStore(Base):
    __tablename__ = "shop_stores"

    id = Column(String(100), primary_key=True)  # canal de venta de Medusa
    name = Column(String(200), nullable=False)
    domains = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ProductShopStore(Base):
    __tablename__ = "product_shop_stores"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    store_id = Column(String(100), ForeignKey("shop_stores.id", ondelete="CASCADE"), primary_key=True)
