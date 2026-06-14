"""Modelos SQLAlchemy — espelham o schema do Supabase."""

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal


def _now() -> datetime:
    return datetime.now(timezone.utc)


from sqlalchemy import String, Boolean, Integer, Date, LargeBinary, Numeric, ForeignKey, Text, Index, UniqueConstraint, CheckConstraint, text
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
        # CNPJ unico POR ORG (#8): o mesmo CNPJ pode existir em orgs distintas
        # (firma A e firma B atendem o mesmo cliente). Linhas legadas com
        # org_id NULL ficam fora da unicidade — NULLs sao distintos no Postgres.
        UniqueConstraint("org_id", "cnpj", name="uq_clientes_org_cnpj"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(18))
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
        # report_id unico POR ORG (#31): substitui a unicidade global. O id e um
        # hex aleatorio de 12 chars (colisao cross-org improvavel), mas a chave
        # multi-tenant correta e (org_id, report_id). Legado org_id NULL: NULLs
        # distintos no Postgres ficam fora da unicidade.
        UniqueConstraint("org_id", "report_id", name="uq_conciliacoes_org_report"),
    )

    id:                   Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:               Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
    cliente_id:           Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="SET NULL"))
    report_id:            Mapped[str]          = mapped_column(Text, nullable=False)
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
        # Cadeia de hash e POR ORG (#3): o ultimo-hash e buscado filtrando por
        # org_id sob FOR UPDATE; o indice (org_id, ts DESC) serve essa busca.
        Index("ix_audit_events_org_ts", "org_id", text("ts DESC")),
    )

    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ts:            Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now, nullable=False)
    # org_id nullable p/ backfill e p/ a cadeia do sistema (eventos sem actor).
    org_id:        Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
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
        # Chave de cache passa a incluir org_id (#30): o cache e por (org, actor,
        # periodo), nao so por actor. Indice cobre a busca do cache valido.
        Index("ix_ai_insights_cache_org_actor_periodo", "org_id", "actor_sub",
              "periodo_dias", text("expira_em DESC")),
    )

    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:       Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
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
        Index("ix_guia_tributo_org", "org_id"),
    )

    id:              Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:      Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    org_id:          Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
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
        Index("ix_contrato_org", "org_id"),
    )

    id:             Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:     Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    org_id:         Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
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
        Index("ix_transacao_disposicao_org", "org_id"),
        # CHECK de dominio (#12): disposicao e o vocabulario do orquestrador
        # (api/matchers/orquestrador.py + status pass-through dos matchers
        # documento/contrato). Texto livre permitia gravar lixo. Manter em
        # sincronia com DISPOSICOES_VALIDAS abaixo se novos estagios surgirem.
        CheckConstraint(
            "disposicao IN ("
            "'TRANSFERENCIA_INTERNA','RESOLVIDO_CADASTRO','RESOLVIDO_BASE',"
            "'RESOLVIDO_NFE','RESOLVIDO_GUIA','RESOLVIDO_CONTRATO',"
            "'TARIFA_BANCARIA','PENDENTE_MATCHER','PENDENTE_REVISAO',"
            "'PENDENTE_FUZZY','NAO_ENCONTRADO','DOC_INVALIDO',"
            "'CONTRATO_NAO_ENCONTRADO','CONTRATO_AMBIGUO'"
            ")",
            name="ck_transacao_disposicao_disposicao",
        ),
    )

    id:             Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    conciliacao_id: Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("conciliacoes.id", ondelete="CASCADE"), nullable=False)
    org_id:         Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
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
    precisa cruzar contra pagamentos no extrato.
    """
    __tablename__ = "documento_fiscal"
    __table_args__ = (
        Index("ix_docfiscal_cliente_chave", "cliente_id", "chave", unique=True),
        Index("ix_docfiscal_cliente_emit", "cliente_id", "emit_cnpj"),
        Index("ix_docfiscal_cliente_data", "cliente_id", "data_emissao"),
        Index("ix_documento_fiscal_org", "org_id"),
    )

    id:                Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:        Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    org_id:            Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
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
        Index("ix_cruzamento_fiscal_org", "org_id"),
        # CHECK de dominio (#12): status do cruzamento doc x pagamento — escrito
        # em api/matchers/cruzamento_fiscal.py. Texto livre virou enum fechado.
        CheckConstraint(
            "status IN ('CASADO','VALOR_DIVERGENTE','SEM_PAGAMENTO','SEM_NF')",
            name="ck_cruzamento_fiscal_status",
        ),
    )

    id:               Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:       Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    org_id:           Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
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
        Index("ix_carta_versao_org", "org_id"),
    )

    id:                Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:        Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    org_id:            Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
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
        Index("ix_conformidade_fornecedor_org", "org_id"),
    )

    id:                       Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:               Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    org_id:                   Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
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


class Usuario(Base):
    """Usuário de uma organização (tenant). Identidade de login multi-org.

    Liga email/senha a um `org_id` — o que o RLS por organização precisa para
    isolar (token carrega `org_id`). `role` é o papel DENTRO da org
    (admin/auditor/user). Email é único globalmente e guardado em lowercase.
    """
    __tablename__ = "usuarios"
    __table_args__ = (
        Index("ix_usuarios_org", "org_id"),
    )

    id:              Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:          Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    email:           Mapped[str]             = mapped_column(Text, unique=True, nullable=False)
    senha_hash:      Mapped[str]             = mapped_column(Text, nullable=False)
    nome:            Mapped[str | None]      = mapped_column(Text)
    role:            Mapped[str]             = mapped_column(String(32), nullable=False, default="user", server_default="user")
    ativo:           Mapped[bool]            = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    ultimo_login_em: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    criado_em:       Mapped[datetime]        = mapped_column(TIMESTAMPTZ, default=_now, nullable=False)
    atualizado_em:   Mapped[datetime]        = mapped_column(TIMESTAMPTZ, default=_now, nullable=False)


# ══════════════════════════════════════════════════════════════════════════
# IC-02 — Apuração CBS/IBS (reforma tributária, LC 214/2025)
# ══════════════════════════════════════════════════════════════════════════


class ApuracaoCBSIBSRow(Base):
    """Apuração CBS/IBS persistida (contrato IC-02 §3.2 → colunas planas).

    Saída da Calculadora CBS/IBS, obtida via ORQUESTRAÇÃO do motor oficial (o
    OrgConc não recalcula tributos). Os grupos gIBSUF/gIBSMun/gCBS/gIS viram
    colunas planas aliquota_*/valor_*; a memória de cálculo por esfera fica em
    `memoria_calculo` (JSONB) para rastreabilidade no laudo (IC-02 §5). Gate de
    proveniência (§4): versao_base + ambiente + fundamentacao_legal obrigatórios.
    """
    __tablename__ = "apuracao_cbs_ibs"
    __table_args__ = (
        Index("ix_apuracao_cbs_ibs_documento", "documento_id"),
        Index("ix_apuracao_cbs_ibs_criado", text("criado_em DESC")),
        Index("ix_apuracao_cbs_ibs_org", "org_id"),
        # Idempotência IC-02 §3.2: a mesma operação (documento + versão da base)
        # não duplica. salvar_apuracao faz UPSERT sobre esta constraint.
        UniqueConstraint("documento_id", "versao_base", name="uq_apuracao_doc_versao"),
    )

    id:                  Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:              Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
    documento_id:        Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), nullable=False)
    versao_base:         Mapped[str]          = mapped_column(String(20), nullable=False)
    ambiente:            Mapped[str]          = mapped_column(String(10), nullable=False)  # PILOTO/PRODUCAO
    motor_versao:        Mapped[str | None]   = mapped_column(Text)
    uf:                  Mapped[str | None]   = mapped_column(String(2))
    municipio_ibge:      Mapped[str | None]   = mapped_column(String(7))
    data_fato_gerador:   Mapped[date | None]  = mapped_column(Date)
    base_calculo_total:  Mapped[float]        = mapped_column(Numeric(15, 2), default=0)
    aliquota_ibs_uf:     Mapped[float]        = mapped_column(Numeric(9, 4), default=0)
    valor_ibs_uf:        Mapped[float]        = mapped_column(Numeric(15, 2), default=0)
    aliquota_ibs_mun:    Mapped[float]        = mapped_column(Numeric(9, 4), default=0)
    valor_ibs_mun:       Mapped[float]        = mapped_column(Numeric(15, 2), default=0)
    aliquota_cbs:        Mapped[float]        = mapped_column(Numeric(9, 4), default=0)
    valor_cbs:           Mapped[float]        = mapped_column(Numeric(15, 2), default=0)
    aliquota_is:         Mapped[float | None] = mapped_column(Numeric(9, 4))
    valor_is:            Mapped[float | None] = mapped_column(Numeric(15, 2))
    v_tot_trib:          Mapped[float]        = mapped_column(Numeric(15, 2), nullable=False, default=0)
    fundamentacao_legal: Mapped[str]          = mapped_column(Text, nullable=False)
    memoria_calculo:     Mapped[dict]         = mapped_column(JSONB, nullable=False)  # {ibs_uf,ibs_mun,cbs,is}
    payload_hash:        Mapped[str | None]   = mapped_column(String(64))
    obtido_em:           Mapped[datetime]     = mapped_column(TIMESTAMPTZ, nullable=False)
    criado_em:           Mapped[datetime]     = mapped_column(TIMESTAMPTZ, default=_now)


class Job(Base):
    """Fila de jobs assíncronos (P1 #9) — tarefas fiscais longas fora do request.

    Claim pelo worker com FOR UPDATE SKIP LOCKED (seguro multi-réplica). RLS:
    policy org_isolation (usuário só vê os jobs da própria org) + worker_access
    (loop do worker enxerga a fila inteira via GUC app.worker). Uploads e
    resultado em BYTEA com TTL de limpeza — ver api/services/job_queue.py.
    """
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_criado", "status", "criado_em"),
        Index("ix_jobs_org", "org_id"),
        # CHECK de dominio (#12): ciclo de vida do job — constantes em
        # api/services/job_queue.py (PENDENTE/EXECUTANDO/CONCLUIDO/ERRO).
        CheckConstraint(
            "status IN ('PENDENTE','EXECUTANDO','CONCLUIDO','ERRO')",
            name="ck_jobs_status",
        ),
    )

    id:             Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:         Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
    tipo:           Mapped[str]              = mapped_column(String(40), nullable=False)
    status:         Mapped[str]              = mapped_column(String(12), nullable=False, default="PENDENTE")
    params:         Mapped[dict]             = mapped_column(JSONB, nullable=False, default=dict)
    arquivos:       Mapped[bytes | None]     = mapped_column(LargeBinary)   # uploads empacotados (ZIP)
    resultado:      Mapped[bytes | None]     = mapped_column(LargeBinary)
    resultado_nome: Mapped[str | None]       = mapped_column(Text)
    resultado_mime: Mapped[str | None]       = mapped_column(Text)
    erro:           Mapped[str | None]       = mapped_column(Text)
    tentativas:     Mapped[int]              = mapped_column(Integer, nullable=False, default=0)
    criado_em:      Mapped[datetime]         = mapped_column(TIMESTAMPTZ, default=_now, nullable=False)
    iniciado_em:    Mapped[datetime | None]  = mapped_column(TIMESTAMPTZ)
    concluido_em:   Mapped[datetime | None]  = mapped_column(TIMESTAMPTZ)
