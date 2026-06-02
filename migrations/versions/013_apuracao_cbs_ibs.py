"""013 — apuracao_cbs_ibs: persistência da apuração CBS/IBS (contrato IC-02)

Cria `apuracao_cbs_ibs` (saída da Calculadora CBS/IBS, IC-02 §3.2). Os grupos
gIBSUF/gIBSMun/gCBS/gIS viram colunas planas aliquota_*/valor_*; a memória de
cálculo por esfera fica em `memoria_calculo` (JSONB) para rastreabilidade no
laudo (§5). Gate de proveniência (§4): versao_base + ambiente + fundamentacao.

ADITIVO e IDEMPOTENTE. Reversível. Rodar online: `alembic upgrade head`.

Revision ID: 013
Revises: 012
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("apuracao_cbs_ibs"):
        return
    op.create_table(
        "apuracao_cbs_ibs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("documento_id", UUID(as_uuid=True), nullable=False),
        sa.Column("versao_base", sa.String(20), nullable=False),
        sa.Column("ambiente", sa.String(10), nullable=False),
        sa.Column("motor_versao", sa.Text),
        sa.Column("uf", sa.String(2)),
        sa.Column("municipio_ibge", sa.String(7)),
        sa.Column("data_fato_gerador", sa.Date),
        sa.Column("base_calculo_total", sa.Numeric(15, 2), server_default="0"),
        sa.Column("aliquota_ibs_uf", sa.Numeric(9, 4), server_default="0"),
        sa.Column("valor_ibs_uf", sa.Numeric(15, 2), server_default="0"),
        sa.Column("aliquota_ibs_mun", sa.Numeric(9, 4), server_default="0"),
        sa.Column("valor_ibs_mun", sa.Numeric(15, 2), server_default="0"),
        sa.Column("aliquota_cbs", sa.Numeric(9, 4), server_default="0"),
        sa.Column("valor_cbs", sa.Numeric(15, 2), server_default="0"),
        sa.Column("aliquota_is", sa.Numeric(9, 4)),
        sa.Column("valor_is", sa.Numeric(15, 2)),
        sa.Column("v_tot_trib", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("fundamentacao_legal", sa.Text, nullable=False),
        sa.Column("memoria_calculo", JSONB, nullable=False),
        sa.Column("payload_hash", sa.String(64)),
        sa.Column("obtido_em", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("criado_em", TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_apuracao_cbs_ibs_documento", "apuracao_cbs_ibs", ["documento_id"])
    op.create_index("ix_apuracao_cbs_ibs_criado", "apuracao_cbs_ibs",
                    [sa.text("criado_em DESC")])


def downgrade() -> None:
    if _has_table("apuracao_cbs_ibs"):
        op.drop_table("apuracao_cbs_ibs")
