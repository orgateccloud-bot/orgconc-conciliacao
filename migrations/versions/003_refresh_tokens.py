"""003 — refresh tokens

Adiciona tabela refresh_tokens para autenticacao com rotacao.
Tokens sao opacos (sha256), nunca JWTs.

Revision ID: 003
Revises: 002
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as TIMESTAMPTZ


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sub", sa.Text, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("emitido_em", TIMESTAMPTZ(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expira_em", TIMESTAMPTZ(timezone=True), nullable=False),
        sa.Column("revogado_em", TIMESTAMPTZ(timezone=True)),
        sa.Column("substituido_por", UUID(as_uuid=True), sa.ForeignKey("refresh_tokens.id")),
        sa.Column("ip", sa.Text),
        sa.Column("user_agent", sa.Text),
    )
    op.create_index(
        "idx_refresh_tokens_sub_ativo",
        "refresh_tokens",
        ["sub"],
        postgresql_where=sa.text("revogado_em IS NULL"),
    )
    op.create_index("idx_refresh_tokens_expira", "refresh_tokens", ["expira_em"])


def downgrade() -> None:
    op.drop_index("idx_refresh_tokens_expira", table_name="refresh_tokens")
    op.drop_index("idx_refresh_tokens_sub_ativo", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
