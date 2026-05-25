"""004 — conciliacoes: usage_latency_ms

Adiciona coluna para registrar latencia (ms) da chamada Claude por conciliacao.
Permite calcular media de performance por modelo no /metrics/modelos.

Revision ID: 004
Revises: 003
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conciliacoes", sa.Column("usage_latency_ms", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("conciliacoes", "usage_latency_ms")
