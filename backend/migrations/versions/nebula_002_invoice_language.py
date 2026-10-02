"""PrintFlow: idioma del PDF de cada factura (invoices.language)

Revision ID: nebula_002
Revises: nebula_001
Create Date: 2026-10-02

NULL = se usa el idioma de la empresa (company_settings.locale). Columna nueva y
nullable: sin reescritura de tabla.
"""
from alembic import op
import sqlalchemy as sa


revision = "nebula_002"
down_revision = "nebula_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("language", sa.String(length=5), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "language")
