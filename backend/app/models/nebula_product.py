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
- ``ProductShopOption``: el artículo como tamaño de otro (en la tienda sale una
  ficha con selector de tamaño) y la caja cuyo coste se suma a su precio.
- ``ShopSettings``: lo común a las tiendas (precio del envío a domicilio).
- ``ShopColor``: nombre de un color en la tienda y si se oculta.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric,
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


class ProductShopOption(Base):
    __tablename__ = "product_shop_options"
    __table_args__ = (
        CheckConstraint("group_id IS NULL OR group_id <> product_id", name="ck_product_shop_options_group"),
        CheckConstraint(
            "customization IN ('none', 'color', 'describe', 'paint')", name="ck_product_shop_options_customization"
        ),
    )

    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    # Producto con tamaños al que pertenece (sale en la tienda como una sola ficha)
    group_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    size_label = Column(String(100), nullable=True)
    position = Column(Integer, nullable=False, default=0)
    # Caja (artículo de embalaje): su coste se suma al precio en la tienda
    box_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    # Qué elige el cliente: none, color (uno), describe (colores + descripción), paint (lo pinta en la web)
    customization = Column(String(20), nullable=False, default="none", server_default="none")


class ShopSettings(Base):
    __tablename__ = "shop_settings"
    __table_args__ = (CheckConstraint("home_shipping_price >= 0", name="ck_shop_settings_shipping"),)

    id = Column(Integer, primary_key=True, default=1)
    home_shipping_price = Column(Numeric(10, 2), nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=True)


class ShopColor(Base):
    """Un color en la tienda: su nombre para el cliente y si se oculta aunque haya bobinas."""
    __tablename__ = "shop_colors"

    color_id = Column(Integer, ForeignKey("colors.id", ondelete="CASCADE"), primary_key=True)
    shop_name = Column(String(100), nullable=True)
    hidden = Column(Boolean, nullable=False, default=False, server_default="false")
    updated_at = Column(DateTime(timezone=True), nullable=True)
