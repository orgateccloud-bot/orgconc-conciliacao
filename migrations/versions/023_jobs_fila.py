"""023 — Tabela jobs: fila assíncrona p/ tarefas fiscais longas (P1 #9)

Fila em Postgres claimada com FOR UPDATE SKIP LOCKED pelo worker embutido nas
réplicas web (api/services/job_queue.py). Laudo/calculadora deixam de bloquear
o request: POST /fiscal/laudo/async devolve job_id; o cliente faz polling em
GET /jobs/{id} e baixa em GET /jobs/{id}/resultado.

RLS (mesmo modelo das demais tabelas tenant-scoped — db/rls/org_isolation.sql):
- org_isolation: usuário só enxerga jobs da própria org (fail-closed).
- superadmin_read: leitura cross-org (GUC app.superadmin).
- worker_access: o LOOP do worker enxerga/atualiza a fila inteira via GUC
  app.worker (setado apenas por api/services/job_queue, nunca por request).

IDEMPOTENTE. Aplicar como OWNER (a migration faz GRANT ao app_orgconc).
Conferir `alembic heads` x base viva antes de migrar (memória de drift Alembic);
validar primeiro no staging (docs/STAGING.md).

Revision ID: 023
Revises: 022
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None

_TABLE = "jobs"

# 1 statement por item: o preDeploy roda Alembic sobre asyncpg, que rejeita
# múltiplos comandos num único execute ("cannot insert multiple commands into
# a prepared statement").
_RLS_STATEMENTS = (
    "ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.jobs FORCE ROW LEVEL SECURITY",
    "ALTER TABLE public.jobs ALTER COLUMN org_id "
    "SET DEFAULT NULLIF(current_setting('app.org_id', true), '')::uuid",
    "DROP POLICY IF EXISTS org_isolation ON public.jobs",
    "CREATE POLICY org_isolation ON public.jobs FOR ALL "
    "USING (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid) "
    "WITH CHECK (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid)",
    "DROP POLICY IF EXISTS superadmin_read ON public.jobs",
    "CREATE POLICY superadmin_read ON public.jobs FOR SELECT "
    "USING (current_setting('app.superadmin', true) = 'on')",
    # Worker da fila: claim/finalização cross-org. Permissiva (OR com a
    # org_isolation); inerte sem app.worker='on' (fail-closed). Só o loop do
    # worker (api/services/job_queue) seta o GUC.
    "DROP POLICY IF EXISTS worker_access ON public.jobs",
    "CREATE POLICY worker_access ON public.jobs FOR ALL "
    "USING (current_setting('app.worker', true) = 'on') "
    "WITH CHECK (current_setting('app.worker', true) = 'on')",
)

_GRANT_APP = "GRANT SELECT, INSERT, UPDATE, DELETE ON public.jobs TO app_orgconc"


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        op.create_table(
            _TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("org_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("orgs.id"), nullable=True),
            sa.Column("tipo", sa.String(40), nullable=False),
            sa.Column("status", sa.String(12), nullable=False,
                      server_default="PENDENTE"),
            sa.Column("params", postgresql.JSONB, nullable=False,
                      server_default=sa.text("'{}'::jsonb")),
            sa.Column("arquivos", sa.LargeBinary, nullable=True),
            sa.Column("resultado", sa.LargeBinary, nullable=True),
            sa.Column("resultado_nome", sa.Text, nullable=True),
            sa.Column("resultado_mime", sa.Text, nullable=True),
            sa.Column("erro", sa.Text, nullable=True),
            sa.Column("tentativas", sa.Integer, nullable=False,
                      server_default="0"),
            sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("iniciado_em", postgresql.TIMESTAMP(timezone=True),
                      nullable=True),
            sa.Column("concluido_em", postgresql.TIMESTAMP(timezone=True),
                      nullable=True),
        )
        op.create_index("ix_jobs_status_criado", _TABLE, ["status", "criado_em"])
        op.create_index("ix_jobs_org", _TABLE, ["org_id"])
    # RLS + policies + grant: idempotente (DROP IF EXISTS antes de cada CREATE).
    for stmt in _RLS_STATEMENTS:
        op.execute(stmt)
    # Role app_orgconc pode não existir fora de prod (staging/local) — pula o GRANT.
    bind = op.get_bind()
    tem_role = bind.execute(sa.text(
        "SELECT 1 FROM pg_roles WHERE rolname = 'app_orgconc'")).first()
    if tem_role:
        op.execute(_GRANT_APP)


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if _TABLE in insp.get_table_names():
        op.drop_table(_TABLE)
