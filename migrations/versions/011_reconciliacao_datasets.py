"""011 — reconciliacao_datasets: storage de datasets em Postgres (substitui disco local)

Cria a tabela `reconciliacao_datasets`, que guarda o dataset de cada conciliacao
(extratos + anomalias + relatorio markdown) como JSONB, indexado pelo report_id
(12 hex).

Motivacao: o storage anterior era em disco local (DATA_DIR/{rid}.json), o que
quebrava escala horizontal — com >1 replica o export caia numa replica sem o
arquivo (404). Em DB o dataset e compartilhado entre replicas. Tambem encerra a
perda silenciosa de relatorios (a janela rolante de 50 arquivos deletava antigos).

ADITIVO e IDEMPOTENTE: so cria a tabela se nao existir; nao toca tabelas
existentes. Reversivel (DROP TABLE). Rodar online: `alembic upgrade head`.

Revision ID: 011
Revises: 010
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("reconciliacao_datasets"):
        return
    op.create_table(
        "reconciliacao_datasets",
        sa.Column("id", sa.String(12), primary_key=True),
        sa.Column("owner_sub", sa.Text, nullable=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("criado_em", TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_reconciliacao_datasets_owner", "reconciliacao_datasets", ["owner_sub"])
    op.create_index("ix_reconciliacao_datasets_criado", "reconciliacao_datasets",
                    [sa.text("criado_em DESC")])


def downgrade() -> None:
    if _has_table("reconciliacao_datasets"):
        op.drop_table("reconciliacao_datasets")
