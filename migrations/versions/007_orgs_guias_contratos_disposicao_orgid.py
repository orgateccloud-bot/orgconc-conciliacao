"""007 — tabelas e colunas faltantes (reconcilia models.py com o histórico)

Cria as tabelas que existiam em api/db/models.py mas NÃO eram criadas por
nenhuma migration Alembic nem pelo SQL do Supabase — fazendo `alembic upgrade
head` num ambiente novo gerar schema incompleto:

- orgs                  (tenant; FK alvo de org_id)
- llm_cost_daily        (custo LLM persistido por dia; usado por db_persistence)
- guia_tributo          (matcher estágio 4)
- contrato              (matcher estágio 5)
- transacao_disposicao  (disposição contábil do orquestrador)

E adiciona a coluna org_id (FK orgs.id) em conciliacoes e transacoes.

IDEMPOTENTE: inspeciona o schema e só cria o que falta. Seguro tanto em
ambiente novo (cria tudo) quanto num banco que foi alterado à mão (no-op nas
partes já existentes). NÃO funciona em modo offline (`--sql`), pois depende de
conexão para inspecionar — rodar com `alembic upgrade head` (online).

Revision ID: 007
Revises: 006
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_column(insp, table: str, col: str) -> bool:
    if not _has_table(insp, table):
        return False
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    insp = _insp()

    # ── orgs (sem dependências; alvo das FKs org_id) ─────────────────────────
    if not _has_table(insp, "orgs"):
        op.create_table(
            "orgs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("nome", sa.Text, nullable=False),
            sa.Column("plano", sa.String(20), server_default="basico"),
            sa.Column("cnpj", sa.Text),
            sa.Column("ativo", sa.Boolean, server_default=sa.text("true")),
            sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
            sa.Column("atualizado_em", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        )

    # ── llm_cost_daily ───────────────────────────────────────────────────────
    if not _has_table(insp, "llm_cost_daily"):
        op.create_table(
            "llm_cost_daily",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("dia", sa.Date, nullable=False),
            sa.Column("custo_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
            sa.Column("chamadas", sa.Integer, nullable=False, server_default="0"),
            sa.Column("atualizado_em", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_llm_cost_daily_dia", "llm_cost_daily", ["dia"], unique=True)

    # ── guia_tributo ─────────────────────────────────────────────────────────
    if not _has_table(insp, "guia_tributo"):
        op.create_table(
            "guia_tributo",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("cliente_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tipo", sa.Text, nullable=False),
            sa.Column("codigo_receita", sa.Text),
            sa.Column("valor", sa.Numeric(15, 2), nullable=False),
            sa.Column("competencia", sa.Text),
            sa.Column("data_vencimento", sa.Date),
            sa.Column("conta_contabil", sa.Text),
            sa.Column("ativo", sa.Boolean, server_default=sa.text("true")),
            sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_guia_tributo_cliente", "guia_tributo", ["cliente_id"])

    # ── contrato ─────────────────────────────────────────────────────────────
    if not _has_table(insp, "contrato"):
        op.create_table(
            "contrato",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("cliente_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("descricao", sa.Text, nullable=False),
            sa.Column("valor", sa.Numeric(15, 2), nullable=False),
            sa.Column("periodicidade", sa.String(20)),
            sa.Column("padrao_memo", sa.Text),
            sa.Column("conta_contabil", sa.Text),
            sa.Column("ativo", sa.Boolean, server_default=sa.text("true")),
            sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_contrato_cliente", "contrato", ["cliente_id"])

    # ── transacao_disposicao ─────────────────────────────────────────────────
    if not _has_table(insp, "transacao_disposicao"):
        op.create_table(
            "transacao_disposicao",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("conciliacao_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("conciliacoes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("transacao_idx", sa.Integer, nullable=False),
            sa.Column("estagio", sa.Integer, nullable=False),
            sa.Column("disposicao", sa.Text, nullable=False),
            sa.Column("contraparte", sa.Text),
            sa.Column("conta_contabil", sa.Text),
            sa.Column("origem", sa.Text),
            sa.Column("flag", sa.Text),
            sa.Column("nfe_chave", sa.String(44)),
            sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_transacao_disposicao_conciliacao", "transacao_disposicao", ["conciliacao_id"])

    # ── colunas org_id (FK orgs.id) ──────────────────────────────────────────
    if not _has_column(insp, "conciliacoes", "org_id"):
        op.add_column(
            "conciliacoes",
            sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=True),
        )
    if not _has_column(insp, "transacoes", "org_id"):
        op.add_column(
            "transacoes",
            sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=True),
        )


def downgrade() -> None:
    insp = _insp()

    if _has_column(insp, "transacoes", "org_id"):
        op.drop_column("transacoes", "org_id")
    if _has_column(insp, "conciliacoes", "org_id"):
        op.drop_column("conciliacoes", "org_id")

    for tbl in ("transacao_disposicao", "contrato", "guia_tributo", "llm_cost_daily", "orgs"):
        if _has_table(insp, tbl):
            op.drop_table(tbl)
