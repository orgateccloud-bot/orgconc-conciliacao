"""Modelos SQLAlchemy — espelham o schema do Supabase."""
import uuid
from datetime import datetime, date, timezone

def _now() -> datetime:
    return datetime.now(timezone.utc)
from sqlalchemy import String, Boolean, Integer, Date, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as _TS, JSONB
TIMESTAMPTZ = _TS(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .client import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Cliente(Base):
    __tablename__ = "clientes"

    id:           Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    nome:         Mapped[str]        = mapped_column(Text, nullable=False)
    cnpj:         Mapped[str | None] = mapped_column(String(18), unique=True)
    email:        Mapped[str | None] = mapped_column(Text)
    telefone:     Mapped[str | None] = mapped_column(Text)
    plano:        Mapped[str]        = mapped_column(String(20), default="basico")
    ativo:        Mapped[bool]       = mapped_column(Boolean, default=True)
    criado_em:    Mapped[datetime]   = mapped_column(TIMESTAMPTZ, default=_now)
    atualizado_em: Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now)

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

    cliente:     Mapped["Cliente | None"]   = relationship(back_populates="conciliacoes")
    transacoes:  Mapped[list["Transacao"]]  = relationship(back_populates="conciliacao")


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
