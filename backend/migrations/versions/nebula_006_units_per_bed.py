"""PrintFlow: piezas por cama de cada artículo

Revision ID: nebula_006
Revises: nebula_005
Create Date: 2026-10-18

products.units_per_bed: cuántas piezas caben en una cama. Con valor, el precio
de un pedido se calcula repartiéndolo en camas (llenas + la del resto) y los
tramos de product_price_tiers son el precio por pieza según cuántas van en la
cama.
"""
from alembic import op
import sqlalchemy as sa


revision = "nebula_006"
down_revision = "nebula_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("units_per_bed", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_products_units_per_bed", "products", "units_per_bed IS NULL OR units_per_bed >= 1")


def downgrade() -> None:
    op.drop_constraint("ck_products_units_per_bed", "products", type_="check")
    op.drop_column("products", "units_per_bed")
