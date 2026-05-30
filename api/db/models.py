"""Modelos SQLAlchemy — espelham o schema do Supabase."""

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal


def _now() -> datetime:
    return datetime.now(timezone.utc)


from sqlalchemy import String, Boolean, Integer, Date, Numeric, ForeignKey, Text
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
    cnpj:         Mapped[str | None] = mapped_column(Text)
    ativo:        Mapped[bool]      = mapped_column(Boolean, default=True)
    criado_em:    Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now)
    atualizado_em: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=_now)


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
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

    cliente: Mapped["Cliente | None"] = relationship(back_populates="conciliacoes")
    transacoes: Mapped[list["Transacao"]] = relationship(back_populates="conciliacao")


class Transacao(Base):
    __tablename__ = "transacoes"

    id:               Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:           Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True)
    conciliacao_id:   Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conciliacoes.id"))
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

    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    actor_sub:    Mapped[str]       = mapped_column(Text, nullable=False)
    periodo_dias: Mapped[int]       = mapped_column(Integer, nullable=False)
    gerado_em:    Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now, nullable=False)
    expira_em:    Mapped[datetime]  = mapped_column(TIMESTAMPTZ, nullable=False)
    payload:      Mapped[dict]      = mapped_column(JSONB, nullable=False)


class LlmCostDaily(Base):
    """Custo Claude API acumulado por dia (UTC) — sobrevive a restart do processo."""
    __tablename__ = "llm_cost_daily"

    id:            Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    dia:           Mapped[date]       = mapped_column(Date, nullable=False, unique=True)
    custo_usd:     Mapped[Decimal]    = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    chamadas:      Mapped[int]        = mapped_column(Integer, nullable=False, default=0)
    atualizado_em: Mapped[datetime]   = mapped_column(TIMESTAMPTZ, default=_now)


class GuiaTributo(Base):
    """Guias tributárias cadastradas pela firma (DARF, DAS, GPS, GNRE, etc.).

    Usado pelo matcher do estágio 4 (api/matchers/guia.py) para casar
    pagamentos no extrato com tributos previamente gerados.
    """
    __tablename__ = "guia_tributo"

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


# ══════════════════════════════════════════════════════════════════════════
# Reconciliacao clean-arch — modelos da camada infra trazidos do branch
# feat/clean-arch-wip. Aditivos (tabelas novas, sem colisao). Necessarios para
# a camada api/infra/repositories importar. Migration correspondente fica
# pendente ate o uso em runtime (refresh tokens ainda nao plugados no main).
# ══════════════════════════════════════════════════════════════════════════


class RefreshToken(Base):
    """Refresh tokens opacos (nunca JWT). Apenas hash sha256 e armazenado."""
    __tablename__ = "refresh_tokens"

    id:              Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    sub:             Mapped[str]             = mapped_column(Text, nullable=False, index=True)
    token_hash:      Mapped[str]             = mapped_column(String(64), unique=True, nullable=False)
    emitido_em:      Mapped[datetime]        = mapped_column(TIMESTAMPTZ, default=_now, nullable=False)
    expira_em:       Mapped[datetime]        = mapped_column(TIMESTAMPTZ, nullable=False)
    revogado_em:     Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    substituido_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("refresh_tokens.id"))
    ip:              Mapped[str | None]      = mapped_column(Text)
    user_agent:      Mapped[str | None]      = mapped_column(Text)
