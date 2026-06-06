"""019 — tabela usuarios (login multi-org; pré-requisito do rollout de RLS)

Cria a tabela de usuários ligados a uma organização (tenant). É o que faltava
para o auth deixar de ser admin-único: cada usuário tem `org_id`, e o login
passa a emitir um JWT carregando esse `org_id` — o valor que a policy
`org_isolation` (db/rls/org_isolation.sql) precisa para isolar no banco.

IDEMPOTENTE: inspeciona o schema e só cria o que falta (seguro em ambiente novo
e em banco já alterado à mão). NÃO funciona em modo offline (`--sql`); rodar com
`alembic upgrade head` (online).

Revision ID: 019
Revises: 018
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    insp = _insp()

    if not _has_table(insp, "usuarios"):
        op.create_table(
            "usuarios",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("orgs.id"), nullable=False),
            sa.Column("email", sa.Text, nullable=False, unique=True),
            sa.Column("senha_hash", sa.Text, nullable=False),
            sa.Column("nome", sa.Text),
            sa.Column("role", sa.String(32), nullable=False, server_default="user"),
            sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.Column("ultimo_login_em", postgresql.TIMESTAMP(timezone=True)),
            sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
            sa.Column("atualizado_em", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_usuarios_org", "usuarios", ["org_id"])


def downgrade() -> None:
    insp = _insp()
    if _has_table(insp, "usuarios"):
        op.drop_table("usuarios")
