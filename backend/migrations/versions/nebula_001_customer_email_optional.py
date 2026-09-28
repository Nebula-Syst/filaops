"""Nebula (fork): users.email nullable para clientes sin email

Revision ID: nebula_001
Revises: 102
Create Date: 2026-09-28

Migraciones propias del fork Nebula-Syst/filaops. Cuelgan de la última de
upstream que existía al crearlas; cuando upstream añada más (103, 104...) habrá
varias cabezas, por eso docker-migrate.sh y docker-entrypoint.sh usan
`alembic upgrade heads`. Las siguientes migraciones del fork deben revisar
nebula_001 (nebula_002, ...).

La restricción UNIQUE se mantiene: PostgreSQL permite varios NULL.
El staff (admin/operator) sigue necesitando email: es su usuario de acceso,
y eso lo validan los esquemas de usuarios, no la base de datos.

Downgrade: solo es posible si no quedan clientes sin email.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "nebula_001"
down_revision = "102"
branch_labels = ("nebula",)
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)
