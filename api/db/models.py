"""Modelos SQLAlchemy — espelham o schema do Supabase."""

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal


def _now() -> datetime:
    return datetime.now(timezone.utc)


from sqlalchemy import String, Boolean, Integer, Date, Numeric, ForeignKey, Text, Index, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as _TS, JSONB

TIMESTAMPTZ = _TS(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .client import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Org(Base):
    __tablename__ = "orgs"

    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    nome:         Mapped[str]       = mapped_column(Text, nullable=False)
    plano:        Mapped[str]       = mapped_column(String(20), default="basico")
    cnpj:         Mapped[str | None] = mapped_column(Text, unique=True)
    ativo:        Mapped[bool]      = mapped_column(Boolean, default=True)
    criado_em:    Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now)
    atualizado_em: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_now)


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (
        Index("idx_clientes_org", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(18), unique=True)
    email: Mapped[str | None] = mapped_column(Text)
    telefone: Mapped[str | None] = mapped_column(Text)
    plano: Mapped[str] = mapped_column(String(20), default="basico")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_now)
    atualizado_em: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_now)

    conciliacoes: Mapped[list["Conciliacao"]] = relationship(back_populates="cliente")


class Conciliacao(Base):
    __tablename__ = "conciliacoes"
    __table_args__ = (
        Index("idx_conciliacoes_cliente", "cliente_id"),
        Index("idx_conciliacoes_criado_em", "criado_em"),
        Index("idx_conciliacoes_org", "org_id"),
    )

    id:                   Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:               Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
    cliente_id:           Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="SET NULL"))
    report_id:            Mapped[str]          = mapped_column(Text, unique=True, nullable=False)
    modo:                 Mapped[str]          = mapped_column(String(20), nullable=False)
    total_transacoes:     Mapped[int]          = mapped_column(Integer, default=0)
    total_anomalias:      Mapped[int]          = mapped_column(Integer, default=0)
    valor_total_credito:  Mapped[float | None] = mapped_column(Numeric(15, 2))
    valor_total_debito:   Mapped[float | None] = mapped_column(Numeric(15, 2))
    periodo_inicio:       Mapped[date | None]  = mapped_column(Date)
    periodo_fim:          Mapped[date | None]  = mapped_column(Date)
    criado_em:            Mapped[datetime]     = mapped_column(TIMESTAMPTZ, default=_now)
    usage_latency_ms:     Mapped[int | None]   = mapped_column(Integer)
    usage_input_tokens:   Mapped[int | None]   = mapped_column(Integer)
    usage_output_tokens:  Mapped[int | None]   = mapped_column(Integer)
    usage_cost_usd:       Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    cliente: Mapped["Cliente | None"] = relationship(back_populates="conciliacoes")
    transacoes: Mapped[list["Transacao"]] = relationship(back_populates="conciliacao")


class Transacao(Base):
    __tablename__ = "transacoes"
    __table_args__ = (
        Index("idx_transacoes_conciliacao", "conciliacao_id"),
        Index("idx_transacoes_cliente", "cliente_id"),
        Index("idx_transacoes_data", "data_lancamento"),
        Index("idx_transacoes_org", "org_id"),
        Index("idx_transacoes_eh_anomalia", "eh_anomalia",
              postgresql_where=text("eh_anomalia = true")),
    )

    id:               Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:           Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
    conciliacao_id:   Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conciliacoes.id", ondelete="CASCADE"))
    cliente_id:       Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="SET NULL"))
    data_lancamento:  Mapped[date]         = mapped_column(Date, nullable=False)
    valor:            Mapped[float]        = mapped_column(Numeric(15, 2), nullable=False)
    memo:             Mapped[str | None]   = mapped_column(Text)
    categoria:        Mapped[str | None]   = mapped_column(Text)
    banco:            Mapped[str | None]   = mapped_column(Text)
    tipo:             Mapped[str | None]   = mapped_column(Text)
    eh_anomalia:      Mapped[bool]         = mapped_column(Boolean, default=False)
    criado_em:        Mapped[datetime]     = mapped_column(TIMESTAMPTZ, default=_now)

    conciliacao: Mapped["Conciliacao | None"] = relationship(back_populates="transacoes")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_ts", text("ts DESC")),
        Index("ix_audit_events_actor_ts", "actor_email", text("ts DESC")),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
    )

    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ts:            Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now, nullable=False)
    actor_email:   Mapped[str | None] = mapped_column(Text)
    actor_sub:     Mapped[str | None] = mapped_column(Text)
    action:        Mapped[str]       = mapped_column(Text, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(Text)
    resource_id:   Mapped[str | None] = mapped_column(Text)
    payload:       Mapped[dict | None] = mapped_column(JSONB)
    payload_hash:  Mapped[str]       = mapped_column(String(64), nullable=False)
    prev_hash:     Mapped[str]       = mapped_column(String(64), nullable=False)
    request_id:    Mapped[str | None] = mapped_column(String(32))


class AiInsightsCache(Base):
    __tablename__ = "ai_insights_cache"
    __table_args__ = (
        Index("ix_ai_insights_cache_actor_periodo", "actor_sub", "periodo_dias",
              text("expira_em DESC")),
    )

    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    actor_sub:    Mapped[str]       = mapped_column(Text, nullable=False)
    periodo_dias: Mapped[int]       = mapped_column(Integer, nullable=False)
    gerado_em:    Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now, nullable=False)
    expira_em:    Mapped[datetime]  = mapped_column(TIMESTAMPTZ, nullable=False)
    payload:      Mapped[dict]      = mapped_column(JSONB, nullable=False)


class LlmCostDaily(Base):
    """Custo Claude API acumulado por dia (UTC) — sobrevive a restart do processo."""
    __tablename__ = "llm_cost_daily"
    __table_args__ = (
        Index("ix_llm_cost_daily_dia", "dia", unique=True),
    )

    id:            Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    dia:           Mapped[date]       = mapped_column(Date, nullable=False)
    custo_usd:     Mapped[Decimal]    = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    chamadas:      Mapped[int]        = mapped_column(Integer, nullable=False, default=0)
    atualizado_em: Mapped[datetime]   = mapped_column(TIMESTAMPTZ, default=_now)


class ReconciliacaoDataset(Base):
    """Dataset de conciliação (extratos + anomalias + relatório markdown) para export.

    Substitui o armazenamento em disco local (DATA_DIR/{rid}.json), que impedia
    escala horizontal: o export caía numa réplica sem o arquivo (404). Em DB o
    dataset é compartilhado entre réplicas. `id` é o report_id (12 hex).
    """
    __tablename__ = "reconciliacao_datasets"
    __table_args__ = (
        Index("ix_reconciliacao_datasets_owner", "owner_sub"),
        Index("ix_reconciliacao_datasets_criado", text("criado_em DESC")),
    )

    id:        Mapped[str]        = mapped_column(String(12), primary_key=True)
    owner_sub: Mapped[str | None] = mapped_column(Text)
    payload:   Mapped[dict]       = mapped_column(JSONB, nullable=False)
    criado_em: Mapped[datetime]   = mapped_column(TIMESTAMPTZ, server_default=text("now()"), nullable=False)


class CnpjCache(Base):
    """Cache de enriquecimento de CNPJ (BrasilAPI/RFB) compartilhado entre réplicas.

    Substitui o JSON local (data/cnpj_cache.json), efêmero no Railway — sem isto o
    enriquecimento cadastral (situação/pós-baixa/MEI) não persiste entre deploys.
    `info` é o CnpjInfo serializado.
    """
    __tablename__ = "cnpj_cache"

    cnpj:          Mapped[str]      = mapped_column(String(14), primary_key=True)
    info:          Mapped[dict]     = mapped_column(JSONB, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("now()"), nullable=False)


class GuiaTributo(Base):
    """Guias tributárias cadastradas pela firma (DARF, DAS, GPS, GNRE, etc.).

    Usado pelo matcher do estágio 4 (api/matchers/guia.py) para casar
    pagamentos no extrato com tributos previamente gerados.
    """
    __tablename__ = "guia_tributo"
    __table_args__ = (
        Index("ix_guia_tributo_cliente", "cliente_id"),
    )

    id:              Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:      Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    tipo:            Mapped[str]          = mapped_column(Text, nullable=False)  # DARF/DAS/GPS/GNRE
    codigo_receita:  Mapped[str | None]   = mapped_column(Text)
    valor:           Mapped[float]        = mapped_column(Numeric(15, 2), nullable=False)
    competencia:     Mapped[str | None]   = mapped_column(Text)  # AAAA-MM
    data_vencimento: Mapped[date | None]  = mapped_column(Date)
    conta_contabil:  Mapped[str | None]   = mapped_column(Text)
    ativo:           Mapped[bool]         = mapped_column(Boolean, default=True)
    criado_em:       Mapped[datetime]     = mapped_column(TIMESTAMPTZ, default=_now)


class Contrato(Base):
    """Contratos recorrentes (aluguel, seguro, leasing, consórcio) — valor fixo.

    Usado pelo matcher do estágio 5 (api/matchers/contrato.py).
    """
    __tablename__ = "contrato"
    __table_args__ = (
        Index("ix_contrato_cliente", "cliente_id"),
    )

    id:             Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:     Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    descricao:      Mapped[str]          = mapped_column(Text, nullable=False)
    valor:          Mapped[float]        = mapped_column(Numeric(15, 2), nullable=False)
    periodicidade:  Mapped[str | None]   = mapped_column(String(20))  # mensal/anual/etc.
    padrao_memo:    Mapped[str | None]   = mapped_column(Text)        # trecho esperado para desempate
    conta_contabil: Mapped[str | None]   = mapped_column(Text)
    ativo:          Mapped[bool]         = mapped_column(Boolean, default=True)
    criado_em:      Mapped[datetime]     = mapped_column(TIMESTAMPTZ, default=_now)


class TransacaoDisposicao(Base):
    """Disposição contábil de cada transação após a cascata de matchers (OrgNeural2).

    Cada conciliação produz N disposições, uma por transação. Disposição = decisão
    final do orquestrador (RESOLVIDO_NFE, RESOLVIDO_GUIA, PENDENTE_REVISAO, etc.).
    """
    __tablename__ = "transacao_disposicao"
    __table_args__ = (
        Index("ix_transacao_disposicao_conciliacao", "conciliacao_id"),
    )

    id:             Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    conciliacao_id: Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("conciliacoes.id", ondelete="CASCADE"), nullable=False)
    transacao_idx:  Mapped[int]          = mapped_column(Integer, nullable=False)
    estagio:        Mapped[int]          = mapped_column(Integer, nullable=False)
    disposicao:     Mapped[str]          = mapped_column(Text, nullable=False)
    contraparte:    Mapped[str | None]   = mapped_column(Text)
    conta_contabil: Mapped[str | None]   = mapped_column(Text)
    origem:         Mapped[str | None]   = mapped_column(Text)
    flag:           Mapped[str | None]   = mapped_column(Text)
    nfe_chave:      Mapped[str | None]   = mapped_column(String(44))
    criado_em:      Mapped[datetime]     = mapped_column(TIMESTAMPTZ, default=_now)


# ══════════════════════════════════════════════════════════════════════════
# Sprint 1 — Módulo de Integração Fiscal
# ══════════════════════════════════════════════════════════════════════════


class DocumentoFiscal(Base):
    """Documento fiscal eletrônico (NF-e / CT-e / NFS-e) persistido após parsing.

    Centraliza os 3 tipos de documentos fiscais brasileiros que a auditoria
    precisa cruzar contra pagamentos no extrato (cf. Constatação VIII LOCAR).
    """
    __tablename__ = "documento_fiscal"
    __table_args__ = (
        Index("ix_docfiscal_cliente_chave", "cliente_id", "chave", unique=True),
        Index("ix_docfiscal_cliente_emit", "cliente_id", "emit_cnpj"),
        Index("ix_docfiscal_cliente_data", "cliente_id", "data_emissao"),
    )

    id:                Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:        Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    tipo:              Mapped[str]         = mapped_column(String(10), nullable=False)  # "NF-e" | "CT-e" | "NFS-e"
    modelo:            Mapped[str]         = mapped_column(String(3), nullable=False)   # "55" | "57" | "65" | "00"
    chave:             Mapped[str]         = mapped_column(String(44), nullable=False)  # chave de acesso (única)
    numero:            Mapped[str | None]  = mapped_column(Text)
    serie:             Mapped[str | None]  = mapped_column(String(10))
    data_emissao:      Mapped[date | None] = mapped_column(Date)
    emit_cnpj:         Mapped[str | None]  = mapped_column(String(14))
    emit_nome:         Mapped[str | None]  = mapped_column(Text)
    emit_uf:           Mapped[str | None]  = mapped_column(String(2))
    dest_cnpj:         Mapped[str | None]  = mapped_column(String(14))
    dest_nome:         Mapped[str | None]  = mapped_column(Text)
    valor_total:       Mapped[float]       = mapped_column(Numeric(15, 2), nullable=False, default=0)
    valor_icms:        Mapped[float]       = mapped_column(Numeric(15, 2), default=0)
    valor_pis:         Mapped[float]       = mapped_column(Numeric(15, 2), default=0)
    valor_cofins:      Mapped[float]       = mapped_column(Numeric(15, 2), default=0)
    valor_iss:         Mapped[float]       = mapped_column(Numeric(15, 2), default=0)
    natureza_operacao: Mapped[str | None]  = mapped_column(Text)
    xml_path:          Mapped[str | None]  = mapped_column(Text)  # caminho no storage
    criado_em:         Mapped[datetime]    = mapped_column(TIMESTAMPTZ, default=_now)


class CruzamentoFiscal(Base):
    """Resultado do cruzamento entre um documento fiscal e uma transação OFX.

    Status:
    - CASADO: documento + transação com mesmo valor/data/CNPJ
    - VALOR_DIVERGENTE: documento + transação mesma data/CNPJ mas valor diferente
    - SEM_PAGAMENTO: documento emitido sem pagamento correspondente no OFX
    - SEM_NF: pagamento OFX sem documento fiscal correspondente (gap fiscal)
    """
    __tablename__ = "cruzamento_fiscal"
    __table_args__ = (
        Index("ix_cruzfiscal_cliente_status", "cliente_id", "status"),
    )

    id:               Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:       Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    documento_id:     Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documento_fiscal.id", ondelete="SET NULL"))
    transacao_id:     Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transacoes.id", ondelete="SET NULL"))
    status:           Mapped[str]         = mapped_column(String(20), nullable=False)
    diferenca_valor:  Mapped[float | None] = mapped_column(Numeric(15, 2))
    diferenca_dias:   Mapped[int | None]   = mapped_column(Integer)
    criado_em:        Mapped[datetime]    = mapped_column(TIMESTAMPTZ, default=_now)


class CartaVersao(Base):
    """Versões geradas da Carta de Constatação por cliente (audit trail).

    Cada vez que `POST /fiscal/gerar-carta` é invocado, uma nova versão é
    persistida com hash do payload + markdown. Permite reemitir e provar
    qual versão foi entregue ao cliente.
    """
    __tablename__ = "carta_versao"
    __table_args__ = (
        Index("ix_carta_cliente_gerado", "cliente_id", text("gerado_em DESC")),
    )

    id:                Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:        Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    versao:            Mapped[str]         = mapped_column(String(50), nullable=False)
    risco_total:       Mapped[float]       = mapped_column(Numeric(15, 2), default=0)
    total_fornecedores: Mapped[int]        = mapped_column(Integer, default=0)
    payload_hash:      Mapped[str]         = mapped_column(String(64), nullable=False)
    markdown:          Mapped[str | None]  = mapped_column(Text)
    gerado_em:         Mapped[datetime]    = mapped_column(TIMESTAMPTZ, default=_now)


class ConformidadeFornecedor(Base):
    """Score de conformidade fiscal de cada fornecedor (CNPJ) por cliente.

    Calculado a partir do cruzamento doc x pagamento. Permite ranquear
    fornecedores por classe de risco e priorizar ações.
    """
    __tablename__ = "conformidade_fornecedor"
    __table_args__ = (
        Index("ix_conformidade_cliente_cnpj", "cliente_id", "cnpj_fornecedor", unique=True),
        Index("ix_conformidade_cliente_risco", "cliente_id", "risco_classe",
              text("risco_tributario_anual DESC")),
    )

    id:                       Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:               Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    cnpj_fornecedor:          Mapped[str]        = mapped_column(String(14), nullable=False)
    razao_social:             Mapped[str | None] = mapped_column(Text)
    periodo_inicio:           Mapped[date | None] = mapped_column(Date)
    periodo_fim:              Mapped[date | None] = mapped_column(Date)
    volume_pago:              Mapped[float]      = mapped_column(Numeric(15, 2), default=0)
    volume_nf:                Mapped[float]      = mapped_column(Numeric(15, 2), default=0)
    conformidade_pct:         Mapped[float]      = mapped_column(Numeric(5, 2), default=0)  # 0..100+
    n_pagamentos:             Mapped[int]        = mapped_column(Integer, default=0)
    n_nfes:                   Mapped[int]        = mapped_column(Integer, default=0)
    risco_classe:             Mapped[str]        = mapped_column(String(10), default="BAIXO")  # BAIXO/MEDIO/ALTO/CRITICO
    risco_tributario_anual:   Mapped[float]      = mapped_column(Numeric(15, 2), default=0)
    flags:                    Mapped[str | None] = mapped_column(Text)  # CSV: REDE_FROTA_TYPE,MEI_SEM_CTE,...
    atualizado_em:            Mapped[datetime]   = mapped_column(TIMESTAMPTZ, default=_now)


class ApuracaoCBSIBS(Base):
    """Apuração CBS/IBS/IS devolvida pela Calculadora (serviço OrgFiscal, sobre a
    API oficial do SERPRO/RFB) para um documento fiscal. Contrato: IC-02.

    Granularidade: uma apuração por (documento_id, versao_base) — índice único;
    gravação idempotente (upsert ao re-apurar). O cálculo NÃO é feito aqui
    (fronteira IC-02 §1.3): esta tabela apenas PERSISTE o resultado. Espelha a
    Migration 013 (apuracao_cbs_ibs).
    """
    __tablename__ = "apuracao_cbs_ibs"
    __table_args__ = (
        Index("ix_apuracao_cbsibs_doc_versao", "documento_id", "versao_base", unique=True),
        Index("ix_apuracao_cbsibs_cliente_doc", "cliente_id", "documento_id"),
        Index("ix_apuracao_cbsibs_cliente_ambiente", "cliente_id", "ambiente"),
    )

    id:                 Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:         Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    documento_id:       Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("documento_fiscal.id", ondelete="CASCADE"), nullable=False)

    # Gate de proveniência (IC-02 §4) — obrigatórios
    versao_base:        Mapped[str]         = mapped_column(String(20), nullable=False)   # ex.: "V0033"
    ambiente:           Mapped[str]         = mapped_column(String(10), nullable=False)   # PILOTO | PRODUCAO
    motor_versao:       Mapped[str | None]  = mapped_column(String(40))                   # ex.: "CalculadorTributo v1.1.0"

    # Contexto da operação
    uf:                 Mapped[str | None]  = mapped_column(String(2))
    municipio_ibge:     Mapped[str | None]  = mapped_column(String(7))
    data_fato_gerador:  Mapped[date | None] = mapped_column(Date)
    base_calculo_total: Mapped[float]       = mapped_column(Numeric(15, 2), default=0)

    # Decomposição por esfera (IC-02 §3.2). Alíquotas em %, conforme API (pIBSUF etc.)
    aliquota_ibs_uf:    Mapped[float | None] = mapped_column(Numeric(9, 6))
    valor_ibs_uf:       Mapped[float]        = mapped_column(Numeric(15, 2), default=0)
    aliquota_ibs_mun:   Mapped[float | None] = mapped_column(Numeric(9, 6))
    valor_ibs_mun:      Mapped[float]        = mapped_column(Numeric(15, 2), default=0)
    aliquota_cbs:       Mapped[float | None] = mapped_column(Numeric(9, 6))
    valor_cbs:          Mapped[float]        = mapped_column(Numeric(15, 2), default=0)
    aliquota_is:        Mapped[float | None] = mapped_column(Numeric(9, 6))
    valor_is:           Mapped[float]        = mapped_column(Numeric(15, 2), default=0)
    v_tot_trib:         Mapped[float]        = mapped_column(Numeric(15, 2), nullable=False, default=0)

    # Rastreabilidade (IC-02 §5)
    fundamentacao_legal: Mapped[str | None]  = mapped_column(Text)
    memoria_calculo:     Mapped[dict | None] = mapped_column(JSONB)   # {gIBSUF, gIBSMun, gCBS, gIS: texto}
    itens:               Mapped[list | None] = mapped_column(JSONB)   # detalhe por item (ncm/cst/cClassTrib/base/valores)
    payload_hash:        Mapped[str | None]  = mapped_column(String(64))

    obtido_em:          Mapped[datetime]    = mapped_column(TIMESTAMPTZ, default=_now)
    criado_em:          Mapped[datetime]    = mapped_column(TIMESTAMPTZ, default=_now)


class RefreshToken(Base):
    """Refresh tokens opacos (sha256) para rotação de sessão. NUNCA são JWT.

    Persistir permite revogação server-side (logout/rotação anti-replay) e
    sobrevivência a restart do processo.
    """
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_sub_ativo", "sub",
              postgresql_where=text("revogado_em IS NULL")),
        Index("ix_refresh_tokens_expira", "expira_em"),
    )

    id:              Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    sub:             Mapped[str]             = mapped_column(Text, nullable=False, index=True)
    # role/cliente_id da sessao: preservam a identidade real ao rotacionar o
    # refresh, evitando que /auth/refresh reemita um access token com role fixo.
    role:            Mapped[str]             = mapped_column(String(32), nullable=False, default="user", server_default="user")
    cliente_id:      Mapped[str | None]      = mapped_column(Text)
    token_hash:      Mapped[str]             = mapped_column(String(64), unique=True, nullable=False)
    emitido_em:      Mapped[datetime]        = mapped_column(TIMESTAMPTZ, default=_now, nullable=False)
    expira_em:       Mapped[datetime]        = mapped_column(TIMESTAMPTZ, nullable=False)
    revogado_em:     Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    substituido_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("refresh_tokens.id"))
    ip:              Mapped[str | None]      = mapped_column(Text)
    user_agent:      Mapped[str | None]      = mapped_column(Text)
