"""PrintFlow: método de entrega del pedido (sales_orders.delivery_method)

Revision ID: nebula_003
Revises: nebula_002
Create Date: 2026-10-06

ship = envío con transportista (lo de siempre), local_delivery = entrega en mano,
pickup = recogida por el cliente. Los pedidos existentes quedan como "ship".
"""
from alembic import op
import sqlalchemy as sa


revision = "nebula_003"
down_revision = "nebula_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_orders",
        sa.Column(
            "delivery_method",
            sa.String(length=20),
            nullable=False,
            server_default="ship",
        ),
    )


def downgrade() -> None:
    op.drop_column("sales_orders", "delivery_method")
