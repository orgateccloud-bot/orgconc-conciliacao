"""005 — ai_insights_cache

Tabela de cache para insights gerados pela IA (Claude). TTL 24h por padrao;
permite refresh manual sem repetir custo de geracao a cada page-load.

Revision ID: 005
Revises: 004
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_insights_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_sub", sa.Text, nullable=False),
        sa.Column("periodo_dias", sa.Integer, nullable=False),
        sa.Column("gerado_em", postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("expira_em", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
    )
    op.create_index(
        "ix_ai_insights_cache_actor_periodo",
        "ai_insights_cache",
        ["actor_sub", "periodo_dias", sa.text("expira_em DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_insights_cache_actor_periodo", table_name="ai_insights_cache")
    op.drop_table("ai_insights_cache")
