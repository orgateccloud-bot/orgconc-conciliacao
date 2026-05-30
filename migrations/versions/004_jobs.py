"""004 — jobs (fila assincrona)

Tabela para acompanhar status de jobs longos (LLM, exportacoes pesadas).

Revision ID: 004
Revises: 003
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as TIMESTAMPTZ


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sub", sa.Text, nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("input_json", sa.Text),
        sa.Column("output_json", sa.Text),
        sa.Column("erro", sa.Text),
        sa.Column("progresso", sa.Integer, nullable=False, server_default="0"),
        sa.Column("criado_em", TIMESTAMPTZ(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("iniciado_em", TIMESTAMPTZ(timezone=True)),
        sa.Column("finalizado_em", TIMESTAMPTZ(timezone=True)),
        sa.CheckConstraint(
            "status IN ('queued','running','done','failed','cancelled')",
            name="ck_jobs_status",
        ),
    )
    op.create_index("idx_jobs_sub", "jobs", ["sub"])
    op.create_index("idx_jobs_tipo", "jobs", ["tipo"])
    op.create_index("idx_jobs_status", "jobs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_jobs_status", table_name="jobs")
    op.drop_index("idx_jobs_tipo", table_name="jobs")
    op.drop_index("idx_jobs_sub", table_name="jobs")
    op.drop_table("jobs")
