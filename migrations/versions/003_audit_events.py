"""003 — audit_events com hash chain

Cria tabela audit_events para trilha de auditoria imutavel.
Cada evento contem sha256 do payload + prev_hash apontando para evento anterior,
formando uma cadeia verificavel (genesis = '0' * 64).

Usado por:
- /audit/timeline (visualizacao na UI dashboard_trust)
- Compliance: prova de integridade sem assinatura criptografica

Revision ID: 003
Revises: 002
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("ts", postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_email", sa.Text),
        sa.Column("actor_sub", sa.Text),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("resource_type", sa.Text),
        sa.Column("resource_id", sa.Text),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(32)),
    )
    op.create_index("ix_audit_events_ts", "audit_events", [sa.text("ts DESC")])
    op.create_index("ix_audit_events_actor_ts", "audit_events",
                    ["actor_email", sa.text("ts DESC")])
    op.create_index("ix_audit_events_resource", "audit_events",
                    ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_resource", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_ts", table_name="audit_events")
    op.drop_index("ix_audit_events_ts", table_name="audit_events")
    op.drop_table("audit_events")
