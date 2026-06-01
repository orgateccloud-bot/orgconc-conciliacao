"""012 — cnpj_cache: enriquecimento de CNPJ em Postgres (substitui JSON local)

Cria `cnpj_cache` (cnpj PK, info JSONB, atualizado_em) para o enriquecimento
cadastral (BrasilAPI/RFB) ser compartilhado entre réplicas e persistir entre
deploys. O JSON local (data/cnpj_cache.json) é efêmero no Railway — sem isto o
heatmap forense (pós-baixa/MEI) não sobrevive em produção.

ADITIVO e IDEMPOTENTE. Reversível. Rodar online: `alembic upgrade head`.

Revision ID: 012
Revises: 011
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("cnpj_cache"):
        return
    op.create_table(
        "cnpj_cache",
        sa.Column("cnpj", sa.String(14), primary_key=True),
        sa.Column("info", JSONB, nullable=False),
        sa.Column("atualizado_em", TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    if _has_table("cnpj_cache"):
        op.drop_table("cnpj_cache")
