"""PrintFlow: colores y personalización en las tiendas online

Revision ID: nebula_010
Revises: nebula_009
Create Date: 2026-10-26

- product_shop_options.customization: qué elige el cliente en la tienda
  (none: nada; color: un color; describe: colores y una descripción de cómo lo
  quiere; paint: lo pinta en la web).
- shop_colors: nombre del color en la tienda (los de PrintFlow vienen del
  catálogo del fabricante, en inglés) y si se oculta aunque haya bobinas.
"""
from alembic import op
import sqlalchemy as sa


revision = "nebula_010"
down_revision = "nebula_009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_shop_options",
        sa.Column("customization", sa.String(20), nullable=False, server_default="none"),
    )
    op.create_check_constraint(
        "ck_product_shop_options_customization",
        "product_shop_options",
        "customization IN ('none', 'color', 'describe', 'paint')",
    )
    op.create_table(
        "shop_colors",
        sa.Column("color_id", sa.Integer(), sa.ForeignKey("colors.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("shop_name", sa.String(100), nullable=True),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("shop_colors")
    op.drop_constraint("ck_product_shop_options_customization", "product_shop_options", type_="check")
    op.drop_column("product_shop_options", "customization")
