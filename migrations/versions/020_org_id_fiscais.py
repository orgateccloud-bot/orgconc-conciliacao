"""020 — org_id nas tabelas fiscais (rollout de RLS por organização)

Adiciona `org_id` (FK orgs.id, NULL) + índice às tabelas tenant-scoped que só
tinham `cliente_id`/`conciliacao_id`, para que a policy `org_isolation`
(db/rls/org_isolation.sql) possa isolá-las por organização no banco.

Coluna NULLABLE de propósito: as tabelas estão vazias (sem backfill); em dados
futuros o `org_id` nasce do contexto da sessão (DEFAULT setado pelo
org_isolation.sql) ou é preenchido pela app a partir do cliente.

IDEMPOTENTE: inspeciona o schema e só adiciona o que falta. NÃO funciona em modo
offline (`--sql`); rodar com `alembic upgrade head` (online).

Revision ID: 020
Revises: 019
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None

# Tabelas tenant-scoped que ainda não tinham org_id (só cliente_id/conciliacao_id).
_TABELAS = [
    "documento_fiscal",
    "cruzamento_fiscal",
    "conformidade_fornecedor",
    "guia_tributo",
    "contrato",
    "carta_versao",
    "transacao_disposicao",
]


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_column(insp, table: str, col: str) -> bool:
    if not _has_table(insp, table):
        return False
    return any(c["name"] == col for c in insp.get_columns(table))


def _has_index(insp, table: str, name: str) -> bool:
    if not _has_table(insp, table):
        return False
    return any(i["name"] == name for i in insp.get_indexes(table))


def upgrade() -> None:
    insp = _insp()
    for t in _TABELAS:
        if not _has_table(insp, t):
            continue
        if not _has_column(insp, t, "org_id"):
            op.add_column(
                t,
                sa.Column("org_id", postgresql.UUID(as_uuid=True),
                          sa.ForeignKey("orgs.id"), nullable=True),
            )
        ix = f"ix_{t}_org"
        if not _has_index(insp, t, ix):
            op.create_index(ix, t, ["org_id"])


def downgrade() -> None:
    insp = _insp()
    for t in _TABELAS:
        ix = f"ix_{t}_org"
        if _has_index(insp, t, ix):
            op.drop_index(ix, table_name=t)
        if _has_column(insp, t, "org_id"):
            op.drop_column(t, "org_id")
