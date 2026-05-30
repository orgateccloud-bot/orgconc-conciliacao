"""006 — audit_log

Tabela para rastreabilidade de mutacoes (item 17).

Revision ID: 006
Revises: 005
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as TIMESTAMPTZ


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("usuario_sub", sa.Text, nullable=False),
        sa.Column("acao", sa.String(20), nullable=False),
        sa.Column("entidade", sa.String(60), nullable=False),
        sa.Column("entidade_id", sa.String(80)),
        sa.Column("payload_hash", sa.String(64)),
        sa.Column("ip", sa.Text),
        sa.Column("user_agent", sa.Text),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("request_id", sa.String(32)),
        sa.Column("criado_em", TIMESTAMPTZ(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_audit_org_criado", "audit_log", ["org_id", "criado_em"])
    op.create_index("idx_audit_sub", "audit_log", ["usuario_sub"])
    op.create_index("idx_audit_acao", "audit_log", ["acao"])


def downgrade() -> None:
    op.drop_index("idx_audit_acao", table_name="audit_log")
    op.drop_index("idx_audit_sub", table_name="audit_log")
    op.drop_index("idx_audit_org_criado", table_name="audit_log")
    op.drop_table("audit_log")
