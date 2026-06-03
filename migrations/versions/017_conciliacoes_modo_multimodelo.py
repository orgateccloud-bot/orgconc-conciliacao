"""017 — adiciona 'multi_modelo' ao CHECK de conciliacoes.modo

O endpoint /conciliar/ofx?multi_modelo=true grava modo='multi_modelo'
(api/routers/conciliacao.py), mas a constraint conciliacoes_modo_check no
banco vivo so admitia ('llm','simulacao','simulacao_local'). Resultado: toda
conciliacao multi-modelo gerava o relatorio normalmente mas falhava ao
persistir a linha de metadados (CheckViolationError) — drift entre o SQL
aplicado no Supabase e o codigo.

As migrations SQL legadas (supabase/migrations/001,002) ja incluiam
'multi_modelo', mas o banco vivo nunca recebeu a atualizacao. Esta migration
fixa a definicao no Alembic (head canonico) para impedir nova divergencia.

Idempotente/robusta ao drift: DROP CONSTRAINT IF EXISTS antes de recriar, pois
o nome pode nao existir em bases recriadas. Reversivel.
"""

from __future__ import annotations

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

_MODOS_NOVO = "('llm','simulacao','simulacao_local','multi_modelo')"
_MODOS_ANTIGO = "('llm','simulacao','simulacao_local')"


def upgrade() -> None:
    op.execute("ALTER TABLE conciliacoes DROP CONSTRAINT IF EXISTS conciliacoes_modo_check")
    op.execute("ALTER TABLE conciliacoes ADD CONSTRAINT conciliacoes_modo_check " f"CHECK (modo IN {_MODOS_NOVO})")


def downgrade() -> None:
    op.execute("ALTER TABLE conciliacoes DROP CONSTRAINT IF EXISTS conciliacoes_modo_check")
    op.execute("ALTER TABLE conciliacoes ADD CONSTRAINT conciliacoes_modo_check " f"CHECK (modo IN {_MODOS_ANTIGO})")
