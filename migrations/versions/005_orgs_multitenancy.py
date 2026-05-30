"""005 — orgs + multi-tenancy

Cria tabela `orgs` e adiciona `org_id` FK em clientes/conciliacoes/transacoes/jobs.
Migration multi-step segura: adiciona NULL, backfill, NOT NULL.

Revision ID: 005
Revises: 004
Create Date: 2026-05-25
"""
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMP as TIMESTAMPTZ


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    # 1. Cria tabela orgs
    op.create_table(
        "orgs",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nome", sa.Text, nullable=False),
        sa.Column("plano", sa.String(20), nullable=False, server_default="basico"),
        sa.Column("cnpj", sa.Text, unique=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("criado_em", TIMESTAMPTZ(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("atualizado_em", TIMESTAMPTZ(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("plano IN ('basico','pro','enterprise')", name="ck_orgs_plano"),
    )

    # 2. Insere org default
    op.execute(f"""
        INSERT INTO orgs (id, nome, plano)
        VALUES ('{DEFAULT_ORG_ID}', 'ORGATEC (default)', 'enterprise')
        ON CONFLICT (id) DO NOTHING
    """)

    # 3. Adiciona org_id NULL em cada tabela
    for tbl in ("clientes", "conciliacoes", "transacoes", "jobs"):
        op.add_column(tbl, sa.Column("org_id", PG_UUID(as_uuid=True), sa.ForeignKey("orgs.id")))
        op.execute(f"UPDATE {tbl} SET org_id = '{DEFAULT_ORG_ID}' WHERE org_id IS NULL")
        op.alter_column(tbl, "org_id", nullable=False)
        op.create_index(f"idx_{tbl}_org", tbl, ["org_id"])


def downgrade() -> None:
    for tbl in ("jobs", "transacoes", "conciliacoes", "clientes"):
        op.drop_index(f"idx_{tbl}_org", table_name=tbl)
        op.drop_column(tbl, "org_id")
    op.drop_table("orgs")
