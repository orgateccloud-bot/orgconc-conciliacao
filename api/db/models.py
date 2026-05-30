"""Modelos SQLAlchemy — espelham o schema do Supabase."""
import uuid
from datetime import datetime, date, timezone

def _now() -> datetime:
    return datetime.now(timezone.utc)
from sqlalchemy import String, Boolean, Integer, Date, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as _TS
TIMESTAMPTZ = _TS(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .client import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# UUID da org "default" — usado para retrocompat com codigo pre-multitenancy.
# Sincronizado com migrations/005_orgs_multitenancy.py.
DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Org(Base):
    """Organizacao (tenant). Item 16 do roadmap."""
    __tablename__ = "orgs"

    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    nome:          Mapped[str]       = mapped_column(Text, nullable=False)
    plano:         Mapped[str]       = mapped_column(String(20), default="basico")
    cnpj:          Mapped[str | None] = mapped_column(Text, unique=True)
    ativo:         Mapped[bool]      = mapped_column(Boolean, default=True)
    criado_em:     Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now)
    atualizado_em: Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now)


class Cliente(Base):
    __tablename__ = "clientes"

    id:           Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:       Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, default=DEFAULT_ORG_ID)
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
    org_id:               Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, default=DEFAULT_ORG_ID)
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

    cliente:     Mapped["Cliente | None"]   = relationship(back_populates="conciliacoes")
    transacoes:  Mapped[list["Transacao"]]  = relationship(back_populates="conciliacao")


class Transacao(Base):
    __tablename__ = "transacoes"

    id:               Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:           Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, default=DEFAULT_ORG_ID)
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


class Job(Base):
    """Jobs assincronos (item 13: fila Arq).

    Status:
    - queued    : enfileirado, aguardando worker
    - running   : worker pegou e esta processando
    - done      : concluido com sucesso (output preenchido)
    - failed    : erro nao recuperavel (erro preenchido)
    - cancelled : cancelado por API
    """
    __tablename__ = "jobs"

    id:            Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:        Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, default=DEFAULT_ORG_ID)
    sub:           Mapped[str]             = mapped_column(Text, nullable=False, index=True)
    tipo:          Mapped[str]             = mapped_column(String(40), nullable=False, index=True)
    status:        Mapped[str]             = mapped_column(String(20), nullable=False, default="queued", index=True)
    input_json:    Mapped[str | None]      = mapped_column(Text)         # JSON serializado
    output_json:   Mapped[str | None]      = mapped_column(Text)
    erro:          Mapped[str | None]      = mapped_column(Text)
    progresso:     Mapped[int]             = mapped_column(Integer, default=0)   # 0-100
    criado_em:     Mapped[datetime]        = mapped_column(TIMESTAMPTZ, default=_now)
    iniciado_em:   Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    finalizado_em: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)


class FeatureFlag(Base):
    """Feature flags (item 26)."""
    __tablename__ = "feature_flags"

    key:            Mapped[str]       = mapped_column(Text, primary_key=True)
    enabled:        Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    # rollout_rules: JSONB com {org_ids: [], plano: [...], percent: 0-100}
    # Mantido como Text aqui (SQLAlchemy ORM ainda sem typing JSONB strict)
    rollout_rules:  Mapped[str]       = mapped_column(Text, default="{}", nullable=False)
    descricao:      Mapped[str | None] = mapped_column(Text)
    atualizado_em:  Mapped[datetime]  = mapped_column(TIMESTAMPTZ, default=_now)
    atualizado_por: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """Audit log de mutacoes (item 17)."""
    __tablename__ = "audit_log"

    id:            Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id:        Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, default=DEFAULT_ORG_ID)
    usuario_sub:   Mapped[str]             = mapped_column(Text, nullable=False, index=True)
    acao:          Mapped[str]             = mapped_column(String(20), nullable=False, index=True)  # create|update|delete|export|llm_call
    entidade:      Mapped[str]             = mapped_column(String(60), nullable=False)
    entidade_id:   Mapped[str | None]      = mapped_column(String(80))
    payload_hash:  Mapped[str | None]      = mapped_column(String(64))   # sha256 hex
    ip:            Mapped[str | None]      = mapped_column(Text)
    user_agent:    Mapped[str | None]      = mapped_column(Text)
    status_code:   Mapped[int]             = mapped_column(Integer, nullable=False)
    request_id:    Mapped[str | None]      = mapped_column(String(32))
    criado_em:     Mapped[datetime]        = mapped_column(TIMESTAMPTZ, default=_now, index=True)


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
