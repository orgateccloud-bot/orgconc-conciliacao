"""021 — remove policies RLS legadas *_org_policy (limpeza de drift)

As policies `<tabela>_org_policy` vêm de uma tentativa antiga de RLS nativa do
Supabase Auth (role `authenticated`, USING org_id = auth.jwt()->>'org_id'').
São INERTES para o backend (que conecta como app_orgconc, fora do role
authenticated), mas representam drift entre o banco e o modelo declarado. O
`db/rls/org_isolation.sql` já as dropa no rollout; esta migration formaliza a
remoção em Alembic (auditável/reversível).

IDEMPOTENTE: DROP POLICY IF EXISTS — no-op nas tabelas onde a policy já não existe
(memória: ~3 ainda existiam no banco vivo). O isolamento real continua na policy
`org_isolation` (não tocada aqui).

⚠️ Aplicar como OWNER (ALEMBIC_DATABASE_URL), não como app_orgconc. Antes de
aplicar em prod: conferir `git log origin/main..HEAD` + `alembic heads` (a base
viva pode estar atrás/bifurcada — ver memória de drift Alembic).

Revision ID: 021
Revises: 020
Create Date: 2026-06-09
"""
from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None

# Tabelas tenant-scoped (mesma lista de db/rls/org_isolation.sql).
_TABELAS = [
    "clientes", "conciliacoes", "transacoes", "apuracao_cbs_ibs",
    "documento_fiscal", "cruzamento_fiscal", "conformidade_fornecedor",
    "guia_tributo", "contrato", "carta_versao", "transacao_disposicao",
]


def upgrade() -> None:
    for t in _TABELAS:
        op.execute(f"DROP POLICY IF EXISTS {t}_org_policy ON public.{t}")


def downgrade() -> None:
    # As policies legadas eram inertes e indesejadas (drift). NÃO recriar:
    # o isolamento real é a policy `org_isolation` (db/rls/org_isolation.sql).
    pass
