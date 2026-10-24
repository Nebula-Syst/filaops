"""PrintFlow: marca de cada bobina y enlaces de los artículos en las tiendas

Revision ID: nebula_007
Revises: nebula_006
Create Date: 2026-10-23

- material_spools.brand: marca de la bobina (Elegoo, Bambu…). El filamento
  (PLA negro) es el artículo; la marca va en la bobina para no duplicar los
  artículos por marca.
- product_shop_links: dónde se vende cada artículo en las tiendas online. Lo
  rellena la sincronización de las tiendas.
"""
from alembic import op
import sqlalchemy as sa


revision = "nebula_007"
down_revision = "nebula_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("material_spools", sa.Column("brand", sa.String(100), nullable=True))
    op.create_table(
        "product_shop_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store", sa.String(200), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_product_shop_links_product_id", "product_shop_links", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_product_shop_links_product_id", table_name="product_shop_links")
    op.drop_table("product_shop_links")
    op.drop_column("material_spools", "brand")
