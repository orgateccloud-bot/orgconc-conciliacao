"""Modelos SQLAlchemy — espelham o schema do Supabase."""
import uuid
from datetime import datetime, date
from sqlalchemy import String, Boolean, Integer, Float, Date, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
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
    criado_em:    Mapped[datetime]   = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    atualizado_em: Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    conciliacoes: Mapped[list["Conciliacao"]] = relationship(back_populates="cliente")


class Conciliacao(Base):
    __tablename__ = "conciliacoes"

    id:                   Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:           Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id"))
    report_id:            Mapped[str]          = mapped_column(Text, unique=True, nullable=False)
    modo:                 Mapped[str]          = mapped_column(String(20), nullable=False)
    total_transacoes:     Mapped[int]          = mapped_column(Integer, default=0)
    total_anomalias:      Mapped[int]          = mapped_column(Integer, default=0)
    valor_total_credito:  Mapped[float | None] = mapped_column(Numeric(15, 2))
    valor_total_debito:   Mapped[float | None] = mapped_column(Numeric(15, 2))
    periodo_inicio:       Mapped[date | None]  = mapped_column(Date)
    periodo_fim:          Mapped[date | None]  = mapped_column(Date)
    criado_em:            Mapped[datetime]     = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    cliente:     Mapped["Cliente | None"]   = relationship(back_populates="conciliacoes")
    transacoes:  Mapped[list["Transacao"]]  = relationship(back_populates="conciliacao")


class Transacao(Base):
    __tablename__ = "transacoes"

    id:               Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    conciliacao_id:   Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conciliacoes.id"))
    cliente_id:       Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id"))
    data_lancamento:  Mapped[date]         = mapped_column(Date, nullable=False)
    valor:            Mapped[float]        = mapped_column(Numeric(15, 2), nullable=False)
    memo:             Mapped[str | None]   = mapped_column(Text)
    categoria:        Mapped[str | None]   = mapped_column(Text)
    banco:            Mapped[str | None]   = mapped_column(Text)
    tipo:             Mapped[str | None]   = mapped_column(Text)
    eh_anomalia:      Mapped[bool]         = mapped_column(Boolean, default=False)
    criado_em:        Mapped[datetime]     = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    conciliacao: Mapped["Conciliacao | None"] = relationship(back_populates="transacoes")
    predicoes:   Mapped[list["MlPredicao"]]   = relationship(back_populates="transacao")


class MlPredicao(Base):
    __tablename__ = "ml_predicoes"

    id:             Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    transacao_id:   Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transacoes.id"))
    modelo:         Mapped[str]          = mapped_column(Text, nullable=False)
    predicao:       Mapped[str]          = mapped_column(Text, nullable=False)
    confianca:      Mapped[float]        = mapped_column(Float, nullable=False)
    confirmado_por: Mapped[str | None]   = mapped_column(Text)
    correto:        Mapped[bool | None]  = mapped_column(Boolean)
    criado_em:      Mapped[datetime]     = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    transacao: Mapped["Transacao | None"] = relationship(back_populates="predicoes")


class FsrsMemoria(Base):
    __tablename__ = "fsrs_memorias"

    id:               Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cliente_id:       Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False)
    pattern_key:      Mapped[str]        = mapped_column(Text, nullable=False)
    pattern_exemplo:  Mapped[str | None] = mapped_column(Text)
    categoria:        Mapped[str]        = mapped_column(Text, nullable=False)
    estabilidade:     Mapped[float]      = mapped_column(Float, default=1.0)
    dificuldade:      Mapped[float]      = mapped_column(Float, default=0.3)
    proxima_revisao:  Mapped[date]       = mapped_column(Date, nullable=False)
    repeticoes:       Mapped[int]        = mapped_column(Integer, default=0)
    lapsos:           Mapped[int]        = mapped_column(Integer, default=0)
    criado_em:        Mapped[datetime]   = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    atualizado_em:    Mapped[datetime]   = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
