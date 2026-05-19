"""002 — drop orphan tables (ml_predicoes, fsrs_memorias)

Schema cleanup: remove tabelas criadas no baseline mas nunca expostas via CRUD.
- ml_predicoes: planejada para ML supervisionado de classificacao (cancelada).
- fsrs_memorias: spaced-repetition (modulo api/db/fsrs.py removido em v0.3).

Revision ID: 002
Revises: 001
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove tabelas orfas. Idempotente: usa IF EXISTS."""
    op.execute("DROP TABLE IF EXISTS ml_predicoes CASCADE")
    op.execute("DROP TABLE IF EXISTS fsrs_memorias CASCADE")


def downgrade() -> None:
    """Recria tabelas (schema legado, para rollback de emergencia)."""
    op.create_table(
        "ml_predicoes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("transacao_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("transacoes.id")),
        sa.Column("modelo", sa.Text, nullable=False),
        sa.Column("predicao", sa.Text, nullable=False),
        sa.Column("confianca", sa.Float, nullable=False),
        sa.Column("confirmado_por", sa.Text),
        sa.Column("correto", sa.Boolean),
        sa.Column("criado_em", sa.dialects.postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
    )
    op.create_table(
        "fsrs_memorias",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cliente_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pattern_key", sa.Text, nullable=False),
        sa.Column("pattern_exemplo", sa.Text),
        sa.Column("categoria", sa.Text, nullable=False),
        sa.Column("estabilidade", sa.Float, server_default="1.0"),
        sa.Column("dificuldade", sa.Float, server_default="0.3"),
        sa.Column("proxima_revisao", sa.Date, nullable=False),
        sa.Column("repeticoes", sa.Integer, server_default="0"),
        sa.Column("lapsos", sa.Integer, server_default="0"),
        sa.Column("criado_em", sa.dialects.postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
        sa.Column("atualizado_em", sa.dialects.postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
    )
