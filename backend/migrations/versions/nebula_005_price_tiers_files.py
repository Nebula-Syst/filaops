"""PrintFlow: precios por cantidad y archivos 3MF de cada artículo

Revision ID: nebula_005
Revises: nebula_004
Create Date: 2026-10-18

product_price_tiers: precio unitario a partir de una cantidad (4 por cama,
200 unidades…). product_files: archivos de impresión del artículo, uno o varios.
"""
from alembic import op
import sqlalchemy as sa


revision = "nebula_005"
down_revision = "nebula_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_price_tiers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("min_quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.UniqueConstraint("product_id", "min_quantity", name="uq_product_price_tiers_qty"),
        sa.CheckConstraint("min_quantity >= 1", name="ck_product_price_tiers_min_qty"),
        sa.CheckConstraint("unit_price >= 0", name="ck_product_price_tiers_price"),
    )
    op.create_index("ix_product_price_tiers_product_id", "product_price_tiers", ["product_id"])

    op.create_table(
        "product_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_file_name", sa.String(255), nullable=False),
        sa.Column("stored_file_name", sa.String(255), nullable=False, unique=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_product_files_product_id", "product_files", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_product_files_product_id", table_name="product_files")
    op.drop_table("product_files")
    op.drop_index("ix_product_price_tiers_product_id", table_name="product_price_tiers")
    op.drop_table("product_price_tiers")
