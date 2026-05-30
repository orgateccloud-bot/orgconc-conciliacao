"""007 — feature_flags (item 26)

Revision ID: 007
Revises: 006
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP as TIMESTAMPTZ


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("rollout_rules", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("descricao", sa.Text),
        sa.Column("atualizado_em", TIMESTAMPTZ(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("atualizado_por", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("feature_flags")
