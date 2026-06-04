"""018 — alinha apuracao_cbs_ibs ao schema canonico do 013 (origin)

Heala um drift: o banco vivo recebeu a variante LOCAL do 013 (colunas extras
`cliente_id`/`itens`, aliquotas Numeric(9,6), `fundamentacao_legal`/
`memoria_calculo`/`obtido_em` nullable, indices proprios), enquanto o codigo
canonico (PR #51: calculadora_cbs_ibs.apurar + fiscal_persistence.salvar_apuracao)
espera o schema do 013 do origin. O `cliente_id` NOT NULL chegaria a quebrar os
INSERTs do code path canonico (que nao preenche essa coluna).

Esta migration converge a tabela para o formato do 013 do origin:
  - DROP das colunas exclusivas da variante local (cliente_id, itens)
  - aliquotas Numeric(9,6) -> Numeric(9,4)
  - fundamentacao_legal / memoria_calculo / obtido_em -> NOT NULL
  - troca os indices locais pelos canonicos (documento + criado DESC)

TODA guardada (IF EXISTS / IF NOT EXISTS / checagens), logo:
  - em DBs novos (criados pelo 013 do origin) e um NO-OP;
  - no banco vivo (variante local) e corretiva.
Tabela vazia no momento da escrita -> alteracoes de tipo/NOT NULL sem risco.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None

_ALIQUOTAS = ("aliquota_ibs_uf", "aliquota_ibs_mun", "aliquota_cbs", "aliquota_is")
_NOT_NULL = ("fundamentacao_legal", "memoria_calculo", "obtido_em")
_IDX_LOCAIS = (
    "ix_apuracao_cbsibs_cliente_ambiente",
    "ix_apuracao_cbsibs_cliente_doc",
    "ix_apuracao_cbsibs_doc_versao",
)


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_table("apuracao_cbs_ibs"):
        return
    # Colunas exclusivas da variante local (dropar indices que dependem delas vem junto).
    op.execute("ALTER TABLE apuracao_cbs_ibs DROP COLUMN IF EXISTS cliente_id")
    op.execute("ALTER TABLE apuracao_cbs_ibs DROP COLUMN IF EXISTS itens")
    # Precisao das aliquotas: 9,6 -> 9,4 (no-op se ja 9,4).
    for col in _ALIQUOTAS:
        if _has_column("apuracao_cbs_ibs", col):
            op.execute(f"ALTER TABLE apuracao_cbs_ibs ALTER COLUMN {col} TYPE numeric(9, 4)")
    # NOT NULL como no 013 do origin (tabela vazia -> seguro).
    for col in _NOT_NULL:
        if _has_column("apuracao_cbs_ibs", col):
            op.execute(f"ALTER TABLE apuracao_cbs_ibs ALTER COLUMN {col} SET NOT NULL")
    # Indices: remove os locais, garante os canonicos.
    for idx in _IDX_LOCAIS:
        op.execute(f"DROP INDEX IF EXISTS {idx}")
    op.execute("CREATE INDEX IF NOT EXISTS ix_apuracao_cbs_ibs_documento " "ON apuracao_cbs_ibs (documento_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_apuracao_cbs_ibs_criado " "ON apuracao_cbs_ibs (criado_em DESC)")


def downgrade() -> None:
    # Best-effort: reverte tipos/nullability e devolve as colunas locais (nullable,
    # pois nao ha como restaurar dados/NOT NULL). Indices canonicos permanecem.
    if not _has_table("apuracao_cbs_ibs"):
        return
    for col in _NOT_NULL:
        if _has_column("apuracao_cbs_ibs", col):
            op.execute(f"ALTER TABLE apuracao_cbs_ibs ALTER COLUMN {col} DROP NOT NULL")
    for col in _ALIQUOTAS:
        if _has_column("apuracao_cbs_ibs", col):
            op.execute(f"ALTER TABLE apuracao_cbs_ibs ALTER COLUMN {col} TYPE numeric(9, 6)")
    op.execute("ALTER TABLE apuracao_cbs_ibs ADD COLUMN IF NOT EXISTS cliente_id uuid")
    op.execute("ALTER TABLE apuracao_cbs_ibs ADD COLUMN IF NOT EXISTS itens jsonb")
