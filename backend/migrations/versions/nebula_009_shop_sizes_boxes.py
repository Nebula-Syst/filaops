"""PrintFlow: tamaños, cajas y envío de las tiendas online

Revision ID: nebula_009
Revises: nebula_008
Create Date: 2026-10-26

- product_shop_options: un artículo puede ser un tamaño de otro (group_id, el
  "producto con tamaños" que sale en la tienda como una sola ficha con
  selector) y llevar una caja (box_id, un artículo de embalaje) cuyo coste se
  suma al precio en la tienda.
- shop_settings: una sola fila con el precio del envío a domicilio.
"""
from alembic import op
import sqlalchemy as sa


revision = "nebula_009"
down_revision = "nebula_008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_shop_options",
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("size_label", sa.String(100), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("box_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("group_id IS NULL OR group_id <> product_id", name="ck_product_shop_options_group"),
    )
    op.create_table(
        "shop_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("home_shipping_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("home_shipping_price >= 0", name="ck_shop_settings_shipping"),
    )


def downgrade() -> None:
    op.drop_table("shop_settings")
    op.drop_table("product_shop_options")
