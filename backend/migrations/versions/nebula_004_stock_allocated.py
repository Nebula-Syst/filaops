"""PrintFlow: unidades de stock apartadas para cada línea de pedido

Revision ID: nebula_004
Revises: nebula_003
Create Date: 2026-10-17

sales_order_lines.stock_allocated_quantity = unidades que ya había en el almacén
y se han apartado para la línea (sin fabricarlas). allocated_quantity sigue
siendo el total listo (stock + lo fabricado por sus órdenes de trabajo).
"""
from alembic import op
import sqlalchemy as sa


revision = "nebula_004"
down_revision = "nebula_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_order_lines",
        sa.Column(
            "stock_allocated_quantity",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("sales_order_lines", "stock_allocated_quantity")
