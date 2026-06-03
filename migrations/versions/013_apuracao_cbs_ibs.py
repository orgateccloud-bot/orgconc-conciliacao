"""013 — Apuração CBS/IBS/IS: persistência da saída da Calculadora (IC-02 §3.2)

Cria a tabela `apuracao_cbs_ibs`, onde o módulo fiscal do OrgConc persiste a
apuração devolvida pela Calculadora CBS/IBS (serviço OrgFiscal, sobre a API
oficial do SERPRO/RFB). Regra de granularidade: uma apuração por
`documento_fiscal` por versão de base (índice único documento_id + versao_base),
o que torna a gravação idempotente (suporta upsert ao re-apurar).

Migração ADITIVA: apenas CREATE TABLE + índices, com FKs para tabelas já
existentes (`clientes` de 001; `documento_fiscal` de 006). Sem ALTER em tabela
existente; sem risco para os dados atuais. Totalmente reversível.

Decisão de modelagem: tabela dedicada (NÃO colunas valor_cbs/ibs em
documento_fiscal) — preserva histórico de apuração e mantém o documento fiscal
imutável. Ver IC-02 §8.2.

Contrato governante: IC-02 (Fronteira Calculadora CBS/IBS ↔ Sistemas Fiscais).
- §3.2  schema de saída ApuracaoCBSIBS (esferas + totais)
- §4    gate de proveniência: `versao_base` + `ambiente` obrigatórios; piloto é provisório
- §5    memória de cálculo obrigatória (rastreabilidade p/ laudo e defesa)

NB de versionamento: o PL-01 chamava esta migração de "007", mas a cabeça da
cadeia já avançou para 012; esta é, portanto, a 013 (down_revision = "012").

Revision ID: 013
Revises: 012
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apuracao_cbs_ibs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("cliente_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("documento_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documento_fiscal.id", ondelete="CASCADE"), nullable=False),

        # --- Gate de proveniência (IC-02 §4) — obrigatórios ---
        sa.Column("versao_base", sa.String(20), nullable=False),   # ex.: "V0033"
        sa.Column("ambiente", sa.String(10), nullable=False),      # PILOTO | PRODUCAO
        sa.Column("motor_versao", sa.String(40)),                  # ex.: "CalculadorTributo v1.1.0"

        # --- Contexto da operação ---
        sa.Column("uf", sa.String(2)),
        sa.Column("municipio_ibge", sa.String(7)),
        sa.Column("data_fato_gerador", sa.Date),
        sa.Column("base_calculo_total", sa.Numeric(15, 2), server_default="0"),

        # --- Decomposição por esfera (IC-02 §3.2). Alíquotas em %, conforme API (pIBSUF etc.) ---
        sa.Column("aliquota_ibs_uf", sa.Numeric(9, 6)),
        sa.Column("valor_ibs_uf", sa.Numeric(15, 2), server_default="0"),
        sa.Column("aliquota_ibs_mun", sa.Numeric(9, 6)),
        sa.Column("valor_ibs_mun", sa.Numeric(15, 2), server_default="0"),
        sa.Column("aliquota_cbs", sa.Numeric(9, 6)),
        sa.Column("valor_cbs", sa.Numeric(15, 2), server_default="0"),
        sa.Column("aliquota_is", sa.Numeric(9, 6)),
        sa.Column("valor_is", sa.Numeric(15, 2), server_default="0"),
        sa.Column("v_tot_trib", sa.Numeric(15, 2), nullable=False, server_default="0"),

        # --- Rastreabilidade (IC-02 §5) ---
        sa.Column("fundamentacao_legal", sa.Text),
        sa.Column("memoria_calculo", postgresql.JSONB),   # {gIBSUF, gIBSMun, gCBS, gIS: texto}
        sa.Column("itens", postgresql.JSONB),             # detalhe por item: ncm/cst/cClassTrib/base/valores
        sa.Column("payload_hash", sa.String(64)),         # hash do payload enviado (idempotência/auditoria)

        sa.Column("obtido_em", postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
        sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
    )
    # Uma apuração por documento por versão de base (idempotente; suporta upsert).
    op.create_index(
        "ix_apuracao_cbsibs_doc_versao",
        "apuracao_cbs_ibs",
        ["documento_id", "versao_base"],
        unique=True,
    )
    op.create_index("ix_apuracao_cbsibs_cliente_doc", "apuracao_cbs_ibs", ["cliente_id", "documento_id"])
    op.create_index("ix_apuracao_cbsibs_cliente_ambiente", "apuracao_cbs_ibs", ["cliente_id", "ambiente"])


def downgrade() -> None:
    op.drop_index("ix_apuracao_cbsibs_cliente_ambiente", table_name="apuracao_cbs_ibs")
    op.drop_index("ix_apuracao_cbsibs_cliente_doc", table_name="apuracao_cbs_ibs")
    op.drop_index("ix_apuracao_cbsibs_doc_versao", table_name="apuracao_cbs_ibs")
    op.drop_table("apuracao_cbs_ibs")
