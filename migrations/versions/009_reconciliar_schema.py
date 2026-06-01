"""009 — reconcilia o schema real com models.py (alembic check limpo)

Fecha o drift histórico entre o schema do banco (baseline SQL + alterações à mão
+ migrations 006/007/008) e api/db/models.py, de modo que `alembic check` não
acuse nenhuma operação pendente — válido tanto no Supabase de produção quanto num
banco novo provisionado só por migrations.

Faz:
- DROPA as 3 tabelas órfãs (jobs, audit_log, feature_flags) — sobras de trabalho
  abandonado, sem referência no código (precedente: 002_drop_orphan_tables).
- SET NOT NULL nas colunas com server_default que o models declara obrigatórias
  (tabelas vazias — seguro).
- DROP NOT NULL nas colunas org_id (clientes/conciliacoes/transacoes) — o models
  as mantém nullable durante o rollout de multi-tenancy.
- ALTER TYPE TEXT->VARCHAR(n) onde o models usa String(n) (cnpj/plano/modo).
- refresh_tokens: renomeia índices idx_*->ix_* (criados à mão antes da 008),
  cria ix_refresh_tokens_sub e dropa o índice extra idx_refresh_tokens_substituido_por.
- Garante clientes.org_id (+FK +idx) e os índices org de conciliacoes/transacoes
  em banco novo (em produção já existem).

IDEMPOTENTE: inspeciona o schema e só altera o que está fora do alvo. Rodar online
(`alembic upgrade head`).

Revision ID: 009
Revises: 008
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


# ── colunas que o models declara NOT NULL mas o banco criou nullable ──────────
# (todas têm server_default na sua migration de origem; tabelas vazias)
_SET_NOT_NULL = [
    ("carta_versao", "risco_total"),
    ("carta_versao", "total_fornecedores"),
    ("carta_versao", "gerado_em"),
    ("conformidade_fornecedor", "volume_pago"),
    ("conformidade_fornecedor", "volume_nf"),
    ("conformidade_fornecedor", "conformidade_pct"),
    ("conformidade_fornecedor", "n_pagamentos"),
    ("conformidade_fornecedor", "n_nfes"),
    ("conformidade_fornecedor", "risco_classe"),
    ("conformidade_fornecedor", "risco_tributario_anual"),
    ("conformidade_fornecedor", "atualizado_em"),
    ("contrato", "ativo"),
    ("contrato", "criado_em"),
    ("cruzamento_fiscal", "criado_em"),
    ("documento_fiscal", "valor_icms"),
    ("documento_fiscal", "valor_pis"),
    ("documento_fiscal", "valor_cofins"),
    ("documento_fiscal", "valor_iss"),
    ("documento_fiscal", "criado_em"),
    ("guia_tributo", "ativo"),
    ("guia_tributo", "criado_em"),
    ("llm_cost_daily", "atualizado_em"),
    ("transacao_disposicao", "criado_em"),
]

# org_id: banco em NOT NULL, models nullable -> afrouxar
_DROP_NOT_NULL = [
    ("clientes", "org_id"),
    ("conciliacoes", "org_id"),
    ("transacoes", "org_id"),
]

# TEXT -> VARCHAR(n) (models usa String(n))
_RETYPE = [
    ("clientes", "cnpj", 18),
    ("clientes", "plano", 20),
    ("conciliacoes", "modo", 20),
    ("orgs", "plano", 20),
]

_ORPHAN_TABLES = ["jobs", "audit_log", "feature_flags"]


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(insp, name):
    return name in insp.get_table_names()


def _column(insp, table, col):
    if not _has_table(insp, table):
        return None
    for c in insp.get_columns(table):
        if c["name"] == col:
            return c
    return None


def _has_index(insp, table, name):
    if not _has_table(insp, table):
        return False
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    insp = _insp()

    # ── tabelas órfãs ────────────────────────────────────────────────────────
    for tbl in _ORPHAN_TABLES:
        if _has_table(insp, tbl):
            op.drop_table(tbl)

    # ── clientes.org_id em banco novo (FK + índice); produção já tem ──────────
    if not _column(insp, "clientes", "org_id"):
        op.add_column(
            "clientes",
            sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=True),
        )
        insp = _insp()
    if not _has_index(insp, "clientes", "idx_clientes_org"):
        op.create_index("idx_clientes_org", "clientes", ["org_id"])
    # índices org de conciliacoes/transacoes (à mão em prod; faltam em banco novo)
    if not _has_index(insp, "conciliacoes", "idx_conciliacoes_org"):
        op.create_index("idx_conciliacoes_org", "conciliacoes", ["org_id"])
    if not _has_index(insp, "transacoes", "idx_transacoes_org"):
        op.create_index("idx_transacoes_org", "transacoes", ["org_id"])

    # ── SET NOT NULL (tabelas vazias) ─────────────────────────────────────────
    for table, col in _SET_NOT_NULL:
        c = _column(insp, table, col)
        if c is not None and c["nullable"]:
            op.alter_column(table, col, nullable=False)

    # ── DROP NOT NULL em org_id ───────────────────────────────────────────────
    for table, col in _DROP_NOT_NULL:
        c = _column(insp, table, col)
        if c is not None and not c["nullable"]:
            op.alter_column(table, col, nullable=True)

    # ── TEXT -> VARCHAR(n) ────────────────────────────────────────────────────
    for table, col, length in _RETYPE:
        c = _column(insp, table, col)
        if c is not None and c["type"].__class__.__name__ == "TEXT":
            op.alter_column(table, col, type_=sa.String(length), existing_type=sa.Text())

    # ── refresh_tokens: idx_* (à mão) -> ix_* (padrão da 008/models) ──────────
    op.execute("ALTER INDEX IF EXISTS idx_refresh_tokens_sub_ativo RENAME TO ix_refresh_tokens_sub_ativo")
    op.execute("ALTER INDEX IF EXISTS idx_refresh_tokens_expira RENAME TO ix_refresh_tokens_expira")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_sub ON refresh_tokens (sub)")
    op.execute("DROP INDEX IF EXISTS idx_refresh_tokens_substituido_por")


def downgrade() -> None:
    """Reverte o reconciliável. NÃO recria as tabelas órfãs dropadas (eram sobras)."""
    insp = _insp()

    op.execute("ALTER INDEX IF EXISTS ix_refresh_tokens_sub_ativo RENAME TO idx_refresh_tokens_sub_ativo")
    op.execute("ALTER INDEX IF EXISTS ix_refresh_tokens_expira RENAME TO idx_refresh_tokens_expira")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_sub")

    for table, col, _length in _RETYPE:
        c = _column(insp, table, col)
        if c is not None and c["type"].__class__.__name__ != "TEXT":
            op.alter_column(table, col, type_=sa.Text(), existing_type=sa.String())

    for table, col in _DROP_NOT_NULL:
        c = _column(insp, table, col)
        if c is not None and c["nullable"]:
            op.alter_column(table, col, nullable=False)

    for table, col in _SET_NOT_NULL:
        c = _column(insp, table, col)
        if c is not None and not c["nullable"]:
            op.alter_column(table, col, nullable=True)
