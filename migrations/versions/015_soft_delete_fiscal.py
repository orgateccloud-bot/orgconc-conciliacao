"""015 — Soft delete em tabelas fiscais

Adiciona `deletado_em TIMESTAMPTZ` em `documento_fiscal`, `cruzamento_fiscal`
e `conformidade_fornecedor`. Documentos fiscais são evidência legal (LC 180/2016
exige retenção de 5 anos); hard delete viola essa obrigação.

Após esta migração, o sistema NUNCA deve usar DELETE nessas tabelas.
Deleções lógicas devem setar `deletado_em = NOW()`. Queries de leitura devem
incluir `WHERE deletado_em IS NULL`.

Migração ADITIVA: apenas ALTER TABLE ADD COLUMN com DEFAULT NULL.
Sem risco para dados existentes. Totalmente reversível.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("documento_fiscal", "cruzamento_fiscal", "conformidade_fornecedor"):
        op.add_column(
            table,
            sa.Column("deletado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        )
        op.create_index(
            f"ix_{table}_deletado_em",
            table,
            ["deletado_em"],
            postgresql_where=sa.text("deletado_em IS NOT NULL"),
        )


def downgrade() -> None:
    for table in ("documento_fiscal", "cruzamento_fiscal", "conformidade_fornecedor"):
        op.drop_index(f"ix_{table}_deletado_em", table_name=table)
        op.drop_column(table, "deletado_em")
