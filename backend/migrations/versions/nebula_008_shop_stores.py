"""PrintFlow: en qué tiendas online se vende cada artículo

Revision ID: nebula_008
Revises: nebula_007
Create Date: 2026-10-25

- shop_stores: las tiendas online (las manda la sincronización de las tiendas;
  el id es el del canal de venta de Medusa).
- product_shop_stores: qué artículos van a cada tienda. Se elige en PrintFlow
  y la tienda lo obedece; la primera sincronización lo rellena con lo que ya
  había en las tiendas.
"""
from alembic import op
import sqlalchemy as sa


revision = "nebula_008"
down_revision = "nebula_007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_stores",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("domains", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "product_shop_stores",
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("store_id", sa.String(100), sa.ForeignKey("shop_stores.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("product_shop_stores")
    op.drop_table("shop_stores")
