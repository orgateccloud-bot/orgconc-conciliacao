"""008 — refresh_tokens

Tabela de refresh tokens opacos (sha256) para rotação de sessão com revogação
server-side. Tokens NUNCA são JWT.

IDEMPOTENTE (inspeciona antes de criar) — seguro em ambiente novo e em banco
já alterado à mão. Rodar online (`alembic upgrade head`).

Revision ID: 008
Revises: 007
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    insp = _insp()
    if "refresh_tokens" in insp.get_table_names():
        return

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("sub", sa.Text, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("emitido_em", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expira_em", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revogado_em", postgresql.TIMESTAMP(timezone=True)),
        sa.Column("substituido_por", postgresql.UUID(as_uuid=True), sa.ForeignKey("refresh_tokens.id")),
        sa.Column("ip", sa.Text),
        sa.Column("user_agent", sa.Text),
    )
    op.create_index("ix_refresh_tokens_sub", "refresh_tokens", ["sub"])
    op.create_index(
        "ix_refresh_tokens_sub_ativo",
        "refresh_tokens",
        ["sub"],
        postgresql_where=sa.text("revogado_em IS NULL"),
    )
    op.create_index("ix_refresh_tokens_expira", "refresh_tokens", ["expira_em"])


def downgrade() -> None:
    insp = _insp()
    if "refresh_tokens" not in insp.get_table_names():
        return
    op.drop_index("ix_refresh_tokens_expira", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_sub_ativo", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_sub", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
