"""006 — Integração Fiscal: DocumentoFiscal + CruzamentoFiscal + ConformidadeFornecedor

Cria as 3 tabelas do módulo de integração fiscal (Sprint 1 do roadmap).

- documento_fiscal: NF-e (mod 55) + CT-e (mod 57) + NFS-e
- cruzamento_fiscal: relacionamento documento x transação (CASADO/SEM_NF/etc.)
- conformidade_fornecedor: score 0-100 por fornecedor, classe de risco

Revision ID: 006
Revises: 005
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # documento_fiscal
    op.create_table(
        "documento_fiscal",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("cliente_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("modelo", sa.String(3), nullable=False),
        sa.Column("chave", sa.String(44), nullable=False),
        sa.Column("numero", sa.Text),
        sa.Column("serie", sa.String(10)),
        sa.Column("data_emissao", sa.Date),
        sa.Column("emit_cnpj", sa.String(14)),
        sa.Column("emit_nome", sa.Text),
        sa.Column("emit_uf", sa.String(2)),
        sa.Column("dest_cnpj", sa.String(14)),
        sa.Column("dest_nome", sa.Text),
        sa.Column("valor_total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("valor_icms", sa.Numeric(15, 2), server_default="0"),
        sa.Column("valor_pis", sa.Numeric(15, 2), server_default="0"),
        sa.Column("valor_cofins", sa.Numeric(15, 2), server_default="0"),
        sa.Column("valor_iss", sa.Numeric(15, 2), server_default="0"),
        sa.Column("natureza_operacao", sa.Text),
        sa.Column("xml_path", sa.Text),
        sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_docfiscal_cliente_chave", "documento_fiscal", ["cliente_id", "chave"], unique=True)
    op.create_index("ix_docfiscal_cliente_emit", "documento_fiscal", ["cliente_id", "emit_cnpj"])
    op.create_index("ix_docfiscal_cliente_data", "documento_fiscal", ["cliente_id", "data_emissao"])

    # cruzamento_fiscal
    op.create_table(
        "cruzamento_fiscal",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("cliente_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("documento_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documento_fiscal.id", ondelete="SET NULL")),
        sa.Column("transacao_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("transacoes.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("diferenca_valor", sa.Numeric(15, 2)),
        sa.Column("diferenca_dias", sa.Integer),
        sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_cruzfiscal_cliente_status", "cruzamento_fiscal", ["cliente_id", "status"])

    # conformidade_fornecedor
    op.create_table(
        "conformidade_fornecedor",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("cliente_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cnpj_fornecedor", sa.String(14), nullable=False),
        sa.Column("razao_social", sa.Text),
        sa.Column("periodo_inicio", sa.Date),
        sa.Column("periodo_fim", sa.Date),
        sa.Column("volume_pago", sa.Numeric(15, 2), server_default="0"),
        sa.Column("volume_nf", sa.Numeric(15, 2), server_default="0"),
        sa.Column("conformidade_pct", sa.Numeric(5, 2), server_default="0"),
        sa.Column("n_pagamentos", sa.Integer, server_default="0"),
        sa.Column("n_nfes", sa.Integer, server_default="0"),
        sa.Column("risco_classe", sa.String(10), server_default="BAIXO"),
        sa.Column("risco_tributario_anual", sa.Numeric(15, 2), server_default="0"),
        sa.Column("flags", sa.Text),
        sa.Column("atualizado_em", postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_conformidade_cliente_cnpj",
        "conformidade_fornecedor",
        ["cliente_id", "cnpj_fornecedor"],
        unique=True,
    )
    op.create_index(
        "ix_conformidade_cliente_risco",
        "conformidade_fornecedor",
        ["cliente_id", "risco_classe", sa.text("risco_tributario_anual DESC")],
    )

    # carta_versao (Sprint 5)
    op.create_table(
        "carta_versao",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("cliente_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("versao", sa.String(50), nullable=False),
        sa.Column("risco_total", sa.Numeric(15, 2), server_default="0"),
        sa.Column("total_fornecedores", sa.Integer, server_default="0"),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("markdown", sa.Text),
        sa.Column("gerado_em", postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_carta_cliente_gerado", "carta_versao", ["cliente_id", sa.text("gerado_em DESC")])


def downgrade() -> None:
    op.drop_index("ix_carta_cliente_gerado", table_name="carta_versao")
    op.drop_table("carta_versao")
    op.drop_index("ix_conformidade_cliente_risco", table_name="conformidade_fornecedor")
    op.drop_index("ix_conformidade_cliente_cnpj", table_name="conformidade_fornecedor")
    op.drop_table("conformidade_fornecedor")
    op.drop_index("ix_cruzfiscal_cliente_status", table_name="cruzamento_fiscal")
    op.drop_table("cruzamento_fiscal")
    op.drop_index("ix_docfiscal_cliente_data", table_name="documento_fiscal")
    op.drop_index("ix_docfiscal_cliente_emit", table_name="documento_fiscal")
    op.drop_index("ix_docfiscal_cliente_chave", table_name="documento_fiscal")
    op.drop_table("documento_fiscal")
