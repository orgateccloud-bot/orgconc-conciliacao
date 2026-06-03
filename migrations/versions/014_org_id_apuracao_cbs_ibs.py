"""014 — org_id em apuracao_cbs_ibs: tenant (firma) para RLS por organização

Alinha `apuracao_cbs_ibs` às demais tabelas tenant-scoped (clientes, conciliacoes,
transacoes) ganhando `org_id` (FK orgs, nullable) + índice. Pré-requisito para a
policy `org_isolation` em db/rls/org_isolation.sql. Nullable enquanto o auth não
popula org por usuário (ver db/rls/README.md) — não ativa RLS por si só.

ADITIVO e IDEMPOTENTE. Reversível. Rodar online: `alembic upgrade head`.

Revision ID: 014
Revises: 013
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    # 013 ainda não rodou: nada a alterar (a coluna nasce com a tabela no futuro).
    if not _has_table("apuracao_cbs_ibs"):
        return
    if _has_column("apuracao_cbs_ibs", "org_id"):
        return
    op.add_column(
        "apuracao_cbs_ibs",
        sa.Column("org_id", UUID(as_uuid=True), nullable=True),
    )
    # FK só se a tabela orgs existir (ambientes mínimos podem não tê-la).
    if _has_table("orgs"):
        op.create_foreign_key(
            "fk_apuracao_cbs_ibs_org", "apuracao_cbs_ibs", "orgs", ["org_id"], ["id"]
        )
    op.create_index("ix_apuracao_cbs_ibs_org", "apuracao_cbs_ibs", ["org_id"])


def downgrade() -> None:
    if not _has_column("apuracao_cbs_ibs", "org_id"):
        return
    op.drop_index("ix_apuracao_cbs_ibs_org", table_name="apuracao_cbs_ibs")
    insp = sa.inspect(op.get_bind())
    fk_names = {fk["name"] for fk in insp.get_foreign_keys("apuracao_cbs_ibs")}
    if "fk_apuracao_cbs_ibs_org" in fk_names:
        op.drop_constraint("fk_apuracao_cbs_ibs_org", "apuracao_cbs_ibs", type_="foreignkey")
    op.drop_column("apuracao_cbs_ibs", "org_id")
