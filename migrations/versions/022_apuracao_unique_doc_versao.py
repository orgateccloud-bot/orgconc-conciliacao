"""022 — UNIQUE (documento_id, versao_base) em apuracao_cbs_ibs (idempotência IC-02)

Garante a idempotência da apuração CBS/IBS (IC-02 §3.2): a mesma operação
(documento_id + versão da base) não gera linhas duplicadas. O `salvar_apuracao`
passa a fazer UPSERT (ON CONFLICT) sobre esta constraint.

ANTES de criar a constraint, DEDUPLICA linhas existentes mantendo a mais recente
(maior criado_em; desempate por id) por (documento_id, versao_base) — necessário
porque o código antigo inseria duplicatas e a constraint falharia se elas
existissem. IDEMPOTENTE: só cria a constraint se faltar.

⚠️ Aplicar como OWNER. Em produção, revisar a deduplicação antes (a linha mantida
é a mais recente — confirme que é a desejada). Conferir `alembic heads` x base
viva antes de migrar (ver memória de drift Alembic).

Revision ID: 022
Revises: 021
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None

_TABLE = "apuracao_cbs_ibs"
_CONSTRAINT = "uq_apuracao_doc_versao"


def _has_constraint(insp, table: str, name: str) -> bool:
    if table not in insp.get_table_names():
        return False
    return any(uc["name"] == name for uc in insp.get_unique_constraints(table))


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        return
    if _has_constraint(insp, _TABLE, _CONSTRAINT):
        return
    # Dedup: mantém a linha mais recente por (documento_id, versao_base).
    op.execute(
        """
        DELETE FROM apuracao_cbs_ibs a
        USING apuracao_cbs_ibs b
        WHERE a.documento_id = b.documento_id
          AND a.versao_base  = b.versao_base
          AND (a.criado_em < b.criado_em
               OR (a.criado_em = b.criado_em AND a.id < b.id))
        """
    )
    op.create_unique_constraint(_CONSTRAINT, _TABLE, ["documento_id", "versao_base"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if _has_constraint(insp, _TABLE, _CONSTRAINT):
        op.drop_constraint(_CONSTRAINT, _TABLE, type_="unique")
