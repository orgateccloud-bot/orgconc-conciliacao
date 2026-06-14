"""024 — Integridade da auditoria + hardening de schema (Onda W1)

Reúne, numa só revisão additiva e idempotente, as correções de integridade
auditadas (achados #1-#4, #8, #12, #30, #31):

1. audit_events.org_id (FK orgs.id, NULL p/ backfill) + índice (org_id, ts DESC).
   A cadeia de hash passa a ser POR ORG; o último-hash é buscado filtrando por
   org sob FOR UPDATE (api/services/audit.py).
2. ai_insights_cache.org_id (FK orgs.id, NULL) + índice composto novo
   (org_id, actor_sub, periodo_dias, expira_em DESC); índice antigo removido.
   A chave de cache passa a incluir org_id (#30).
3. clientes: UNIQUE(cnpj) global → UNIQUE(org_id, cnpj). O mesmo CNPJ pode
   existir em orgs distintas (#8). Linhas legadas org_id NULL ficam fora da
   unicidade (NULLs distintos no Postgres) — aceitável.
4. conciliacoes: UNIQUE(report_id) global → UNIQUE(org_id, report_id) (#31).
5. CHECK de domínio (#12) em:
   - transacao_disposicao.disposicao (vocabulário do orquestrador),
   - cruzamento_fiscal.status (CASADO/VALOR_DIVERGENTE/SEM_PAGAMENTO/SEM_NF),
   - jobs.status (PENDENTE/EXECUTANDO/CONCLUIDO/ERRO).
   Cada CHECK valida as linhas existentes antes de criar (aborta se houver valor
   fora do domínio, em vez de criar NOT VALID silencioso).
6. RLS de audit_events: tratado em db/rls/org_isolation.sql (aplicado como owner).

asyncpg rejeita múltiplos comandos por prepared statement → 1 statement por
op.execute(). IDEMPOTENTE: inspeciona o schema e só aplica o que falta.
NÃO roda em modo offline (--sql). Conferir `alembic heads` x base viva e validar
no staging antes de prod (memória de drift Alembic).

Revision ID: 024
Revises: 023
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


# ── Vocabulários dos CHECK de domínio (#12) ────────────────────────────────
# Mantenha em sincronia com api/db/models.py e os escritores citados.
_DISPOSICOES = (
    "TRANSFERENCIA_INTERNA", "RESOLVIDO_CADASTRO", "RESOLVIDO_BASE",
    "RESOLVIDO_NFE", "RESOLVIDO_GUIA", "RESOLVIDO_CONTRATO",
    "TARIFA_BANCARIA", "PENDENTE_MATCHER", "PENDENTE_REVISAO",
    "PENDENTE_FUZZY", "NAO_ENCONTRADO", "DOC_INVALIDO",
    "CONTRATO_NAO_ENCONTRADO", "CONTRATO_AMBIGUO",
)
_CRUZAMENTO_STATUS = ("CASADO", "VALOR_DIVERGENTE", "SEM_PAGAMENTO", "SEM_NF")
_JOBS_STATUS = ("PENDENTE", "EXECUTANDO", "CONCLUIDO", "ERRO")


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


def _unique_names(insp, table: str) -> list[str]:
    if not _has_table(insp, table):
        return []
    return [uc["name"] for uc in insp.get_unique_constraints(table) if uc.get("name")]


def _has_check(insp, table: str, name: str) -> bool:
    if not _has_table(insp, table):
        return False
    return any(cc.get("name") == name for cc in insp.get_check_constraints(table))


def _in_list_sql(col: str, valores: tuple[str, ...]) -> str:
    itens = ", ".join("'" + v + "'" for v in valores)
    return col + " IN (" + itens + ")"


def _add_org_id(insp, table: str) -> None:
    """Adiciona org_id (FK orgs.id, NULL) + índice (org_id, ts DESC), idempotente."""
    if not _has_table(insp, table):
        return
    if not _has_column(insp, table, "org_id"):
        op.add_column(
            table,
            sa.Column("org_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("orgs.id"), nullable=True),
        )


def _swap_unique(insp, table: str, coluna: str, novo_nome: str) -> None:
    """Troca o UNIQUE global da coluna pelo UNIQUE composto (org_id, coluna).

    Dropa qualquer unique constraint que cubra exatamente [coluna] (nome
    auto-gerado pelo Postgres = '<table>_<col>_key', mas inspeciona p/ robustez)
    e cria a composta. Idempotente: se a composta já existe, não recria.
    """
    if not _has_table(insp, table):
        return
    if novo_nome in _unique_names(insp, table):
        return  # composta já existe — nada a fazer

    # Dropa a(s) unique constraint(s) de coluna única [coluna].
    for uc in insp.get_unique_constraints(table):
        cols = uc.get("column_keys") or uc.get("column_names") or []
        if list(cols) == [coluna] and uc.get("name"):
            op.drop_constraint(uc["name"], table, type_="unique")

    op.create_unique_constraint(novo_nome, table, ["org_id", coluna])


def _add_check(insp, table: str, coluna: str, nome: str, valores: tuple[str, ...]) -> None:
    """Cria CHECK col IN (...) validando as linhas existentes antes.

    Se houver valor fora do domínio, aborta com erro claro (não cria NOT VALID).
    Idempotente: pula se o CHECK já existe.
    """
    if not _has_table(insp, table) or not _has_column(insp, table, coluna):
        return
    if _has_check(insp, table, nome):
        return

    bind = op.get_bind()
    cond = _in_list_sql(coluna, valores)
    invalidos = bind.execute(sa.text(
        "SELECT count(*) FROM public." + table
        + " WHERE " + coluna + " IS NOT NULL AND NOT (" + cond + ")"
    )).scalar()
    if invalidos and int(invalidos) > 0:
        raise RuntimeError(
            "024: " + table + "." + coluna + " tem " + str(invalidos)
            + " linha(s) fora do domínio " + str(valores)
            + " — corrija os dados antes de aplicar o CHECK " + nome + "."
        )
    op.create_check_constraint(nome, table, cond)


def upgrade() -> None:
    insp = _insp()

    # 1. org_id em audit_events + índice (org_id, ts DESC) p/ a busca do
    #    último-hash da cadeia por org (FOR UPDATE).
    _add_org_id(insp, "audit_events")
    insp = _insp()
    if _has_table(insp, "audit_events") and not _has_index(insp, "audit_events", "ix_audit_events_org_ts"):
        op.create_index("ix_audit_events_org_ts", "audit_events",
                        ["org_id", sa.text("ts DESC")])

    # 2. org_id em ai_insights_cache + novo índice composto; remove o antigo.
    _add_org_id(insp, "ai_insights_cache")
    insp = _insp()
    if _has_table(insp, "ai_insights_cache"):
        if not _has_index(insp, "ai_insights_cache", "ix_ai_insights_cache_org_actor_periodo"):
            op.create_index(
                "ix_ai_insights_cache_org_actor_periodo",
                "ai_insights_cache",
                ["org_id", "actor_sub", "periodo_dias", sa.text("expira_em DESC")],
            )
        if _has_index(insp, "ai_insights_cache", "ix_ai_insights_cache_actor_periodo"):
            op.drop_index("ix_ai_insights_cache_actor_periodo", table_name="ai_insights_cache")

    # 3. clientes: UNIQUE(cnpj) → UNIQUE(org_id, cnpj).
    insp = _insp()
    _swap_unique(insp, "clientes", "cnpj", "uq_clientes_org_cnpj")

    # 4. conciliacoes: UNIQUE(report_id) → UNIQUE(org_id, report_id).
    insp = _insp()
    _swap_unique(insp, "conciliacoes", "report_id", "uq_conciliacoes_org_report")

    # 5. CHECK de domínio (#12) — valida dados existentes antes.
    insp = _insp()
    _add_check(insp, "transacao_disposicao", "disposicao",
               "ck_transacao_disposicao_disposicao", _DISPOSICOES)
    _add_check(insp, "cruzamento_fiscal", "status",
               "ck_cruzamento_fiscal_status", _CRUZAMENTO_STATUS)
    _add_check(insp, "jobs", "status",
               "ck_jobs_status", _JOBS_STATUS)


def downgrade() -> None:
    insp = _insp()

    # 5. CHECK de domínio.
    for table, nome in (
        ("jobs", "ck_jobs_status"),
        ("cruzamento_fiscal", "ck_cruzamento_fiscal_status"),
        ("transacao_disposicao", "ck_transacao_disposicao_disposicao"),
    ):
        if _has_check(insp, table, nome):
            op.drop_constraint(nome, table, type_="check")

    # 4 + 3. Reverte uniques compostas para a global de coluna única.
    insp = _insp()
    if "uq_conciliacoes_org_report" in _unique_names(insp, "conciliacoes"):
        op.drop_constraint("uq_conciliacoes_org_report", "conciliacoes", type_="unique")
        op.create_unique_constraint("conciliacoes_report_id_key", "conciliacoes", ["report_id"])
    if "uq_clientes_org_cnpj" in _unique_names(insp, "clientes"):
        op.drop_constraint("uq_clientes_org_cnpj", "clientes", type_="unique")
        op.create_unique_constraint("clientes_cnpj_key", "clientes", ["cnpj"])

    # 2. ai_insights_cache: restaura índice antigo, remove o novo + org_id.
    insp = _insp()
    if _has_table(insp, "ai_insights_cache"):
        if not _has_index(insp, "ai_insights_cache", "ix_ai_insights_cache_actor_periodo"):
            op.create_index(
                "ix_ai_insights_cache_actor_periodo",
                "ai_insights_cache",
                ["actor_sub", "periodo_dias", sa.text("expira_em DESC")],
            )
        if _has_index(insp, "ai_insights_cache", "ix_ai_insights_cache_org_actor_periodo"):
            op.drop_index("ix_ai_insights_cache_org_actor_periodo", table_name="ai_insights_cache")
        if _has_column(insp, "ai_insights_cache", "org_id"):
            op.drop_column("ai_insights_cache", "org_id")

    # 1. audit_events: índice + org_id.
    insp = _insp()
    if _has_index(insp, "audit_events", "ix_audit_events_org_ts"):
        op.drop_index("ix_audit_events_org_ts", table_name="audit_events")
    if _has_column(insp, "audit_events", "org_id"):
        op.drop_column("audit_events", "org_id")
