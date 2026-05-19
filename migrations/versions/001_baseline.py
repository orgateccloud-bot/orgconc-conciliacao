"""baseline — schema inicial ja aplicado via supabase/migrations/001_schema_inicial.sql

Esta migration eh um marker: o schema ja existe no banco.
Use `alembic stamp 001` para marcar o banco como estando neste ponto.
Migrations futuras (002+) sao incrementais a partir daqui.

Revision ID: 001
Revises:
Create Date: 2026-05-19
"""
from alembic import op


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Schema ja foi aplicado externamente. Esta migration eh apenas o ponto de partida."""
    # Nao faz nada — schema ja existe no banco (criado por supabase/migrations/001_schema_inicial.sql).
    # Para novos ambientes, rodar o SQL antes ou usar `alembic upgrade head` apos
    # gerar uma migration completa via `alembic revision --autogenerate`.
    pass


def downgrade() -> None:
    """Sem rollback do baseline. Use o SQL original como referencia."""
    pass
