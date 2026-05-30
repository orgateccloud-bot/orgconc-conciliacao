"""Pydantic response models — usados em `response_model=` para gerar OpenAPI correto.

Mantido em arquivo separado de `api/schemas.py` (que tem os request models)
para evitar churn de imports nos routers existentes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Health ──────────────────────────────────────────────────────────────────

class DependencyStatus(BaseModel):
    status: str = Field(..., description="ok | degraded | down | skip")
    latency_ms: float | None = None
    motivo: str | None = None
    erro: str | None = None
    mensagem: str | None = None
    free_mb: int | None = None
    total_mb: int | None = None
    path: str | None = None
    configured: bool | None = None
    modo: str | None = None


class HealthResponse(BaseModel):
    status: str = Field(..., description="ok | degraded | down")
    versao: str
    uptime_s: float
    api_key_configured: bool
    banco_dados: str
    dependencies: dict[str, DependencyStatus]


class LiveResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    ready: bool
    database: str
    anthropic: str


# ── Auth ────────────────────────────────────────────────────────────────────

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_emitted: bool = False
    refresh_ttl_days: int | None = None
    refresh_motivo: str | None = None


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_emitted: bool = True
    refresh_ttl_days: int


class LogoutResponse(BaseModel):
    detail: str
    revogados: int | None = None


class MeResponse(BaseModel):
    sub: str
    email: str | None = None
    role: str


# ── Cliente ─────────────────────────────────────────────────────────────────

class ClienteResponse(BaseModel):
    id: str
    nome: str
    cnpj: str | None = None
    email: str | None = None
    telefone: str | None = None
    plano: str
    ativo: bool | None = None
    criado_em: str | None = None


# ── Conciliacao (listagem) ──────────────────────────────────────────────────

class ConciliacaoExports(BaseModel):
    html: str
    xlsx: str
    pdf: str


class ConciliacaoListItem(BaseModel):
    id: str
    report_id: str
    cliente_id: str | None = None
    modo: str
    total_transacoes: int
    total_anomalias: int
    periodo_inicio: str | None = None
    periodo_fim: str | None = None
    criado_em: str | None = None
    exports: ConciliacaoExports


# ── Conciliacao (processamento) ─────────────────────────────────────────────

class ExtratoResumo(BaseModel):
    arquivo: str
    conta: str
    qtd: int


class AnomaliaResponse(BaseModel):
    severidade: str
    tipo: str
    titulo: str
    conta: str
    valor: float
    detalhe: str


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class ModeloMultiResultado(BaseModel):
    modelo: str
    label: str
    input_tokens: int = 0
    output_tokens: int = 0
    erro: str | None = None


class PersistenciaStatus(BaseModel):
    status: str
    motivo: str | None = None
    transacoes_persistidas: int | None = None
    erro: str | None = None
    mensagem: str | None = None


class ConciliacaoResponse(BaseModel):
    """Resposta de /conciliar/* — campos variam conforme modo."""
    modo: str
    report_id: str
    extratos: list[ExtratoResumo] = []
    anomalias: list[AnomaliaResponse] = []
    relatorio_md: str
    relatorio_html: str | None = None
    persistencia: PersistenciaStatus | None = None
    usage: TokenUsage | None = None
    # Apenas para modo=multi_modelo
    score_consenso: float | None = None
    modelos: list[ModeloMultiResultado] | None = None
    relatorios_individuais: dict[str, str] | None = None
    # Apenas para modo=claude_llm
    modelo: str | None = None
    modelo_id: str | None = None
    modelo_label: str | None = None
    # Apenas para CSV
    extrato: str | None = None
    razao: str | None = None


# ── Erro padrao (RFC 7807) ──────────────────────────────────────────────────

class ProblemDetailsResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str | dict | None = None
    instance: str
    request_id: str
    errors: list[dict[str, Any]] | None = None
