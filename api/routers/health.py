"""Health checks.

- /              -> banner + lista de endpoints (publico)
- /health        -> resumo completo (publico) com status de cada dep
- /health/live   -> liveness K8s: sempre 200 se o processo esta de pe
- /health/ready  -> readiness K8s: 200 so se DB (critica) + Anthropic OK
- /logo-base64   -> data URI do logo (usado pelo render HTML/PDF)
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import text as sql_text

from api.core.config import DATA_DIR, DB_DISPONIVEL, SessionLocal, VERSION
from api.core.templates import LOGO_DATA_URI
from api.schemas_responses import HealthResponse, LiveResponse, ReadyResponse

router = APIRouter()
log = logging.getLogger("orgconc.health")

_BOOT_TS = time.time()
_CHECK_TIMEOUT_S = 3.0


# ── Checks individuais ──────────────────────────────────────────────────────

async def _check_database() -> dict[str, Any]:
    if not DB_DISPONIVEL or SessionLocal is None:
        return {"status": "skip", "motivo": "nao_configurado"}
    t0 = time.perf_counter()
    try:
        async with SessionLocal() as db:
            await asyncio.wait_for(
                db.execute(sql_text("SELECT 1")),
                timeout=_CHECK_TIMEOUT_S,
            )
        return {"status": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except asyncio.TimeoutError:
        return {"status": "down", "erro": "timeout"}
    except Exception as exc:
        return {"status": "down", "erro": type(exc).__name__, "mensagem": str(exc)[:200]}


def _check_anthropic_config() -> dict[str, Any]:
    # Nao chamamos a API real (evita custo + latencia em healthcheck).
    # So validamos que a chave existe.
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return {"status": "skip", "motivo": "nao_configurado"}
    if not key.startswith("sk-ant-"):
        return {"status": "down", "erro": "formato_invalido"}
    return {"status": "ok", "configured": True}


def _check_serpro_config() -> dict[str, Any]:
    has_demo = bool(os.environ.get("ORGCONC_SERPRO_DEMO_TOKEN", "").strip())
    has_oauth = bool(
        os.environ.get("ORGCONC_SERPRO_CONSUMER_KEY", "").strip()
        and os.environ.get("ORGCONC_SERPRO_CONSUMER_SECRET", "").strip()
    )
    has_path = bool(os.environ.get("ORGCONC_SERPRO_CLIENT_PATH", "").strip())
    if not (has_demo or has_oauth or has_path):
        return {"status": "skip", "motivo": "nao_configurado"}
    return {
        "status": "ok",
        "modo": "oauth2" if has_oauth else ("demo" if has_demo else "plugin"),
    }


def _check_redis() -> dict[str, Any]:
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return {"status": "skip", "motivo": "nao_configurado"}
    try:
        import redis as _redis
        t0 = time.perf_counter()
        client = _redis.Redis.from_url(url, socket_connect_timeout=_CHECK_TIMEOUT_S, socket_timeout=_CHECK_TIMEOUT_S)
        client.ping()
        return {"status": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as exc:
        return {"status": "down", "erro": type(exc).__name__, "mensagem": str(exc)[:200]}


def _check_data_dir() -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(str(DATA_DIR))
        free_mb = round(usage.free / (1024 * 1024))
        status = "ok" if free_mb > 200 else ("degraded" if free_mb > 50 else "down")
        return {
            "status": status,
            "path": str(DATA_DIR),
            "free_mb": free_mb,
            "total_mb": round(usage.total / (1024 * 1024)),
        }
    except Exception as exc:
        return {"status": "down", "erro": type(exc).__name__, "mensagem": str(exc)[:200]}


def _agregar(dependencies: dict[str, dict[str, Any]], *, criticas: set[str]) -> str:
    """Calcula status global:
    - down se qualquer critica esta down
    - degraded se nao-critica esta down ou critica esta degraded
    - ok caso contrario
    """
    for nome, dep in dependencies.items():
        if dep["status"] == "down" and nome in criticas:
            return "down"
    for nome, dep in dependencies.items():
        if dep["status"] in ("down", "degraded") and nome not in criticas:
            return "degraded"
        if dep["status"] == "degraded" and nome in criticas:
            return "degraded"
    return "ok"


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/")
def root():
    return {
        "service": "Conciliacao Bancaria API",
        "version": VERSION,
        "endpoints": [
            "/health", "/health/live", "/health/ready", "/docs",
            "/v1/conciliar/ofx", "/v1/conciliar/csv",
            "/v1/export/html/{report_id}", "/v1/export/xlsx/{report_id}", "/v1/export/pdf/{report_id}",
            "/v1/clientes", "/v1/conciliacoes",
            "/auth/login", "/auth/refresh", "/auth/logout", "/auth/me",
            "/v1/serpro/cpf", "/v1/serpro/cnpj",
        ],
        "api_versioning": "Endpoints de negocio sob /v1. Rotas sem /v1 mantidas por 1 release (compat).",
    }


@router.get("/health", response_model=HealthResponse)
async def health(response: Response):
    """Health completo: status + uptime + cada dependencia.

    Status HTTP mapeia para o status agregado:
    - ok         -> 200
    - degraded   -> 200 (ainda servimos requisicoes)
    - down       -> 503 (alguma critica caiu)
    """
    # Roda checks IO-bound concorrentemente (DB + Redis em paralelo)
    db_task = _check_database()
    db_result = await db_task

    dependencies = {
        "database": db_result,
        "anthropic": _check_anthropic_config(),
        "serpro": _check_serpro_config(),
        "redis": _check_redis(),
        "data_dir": _check_data_dir(),
    }
    # Database e critica para a maioria das operacoes; data_dir tambem
    status = _agregar(dependencies, criticas={"database", "data_dir"})
    if status == "down":
        response.status_code = 503
    return {
        "status": status,
        "versao": VERSION,
        "uptime_s": round(time.time() - _BOOT_TS, 1),
        # Compat com clientes antigos
        "api_key_configured": dependencies["anthropic"]["status"] == "ok",
        "banco_dados": dependencies["database"]["status"],
        "dependencies": dependencies,
    }


@router.get("/health/live", response_model=LiveResponse, include_in_schema=False)
def health_live():
    """Liveness probe: sempre 200 se o processo responde."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=ReadyResponse)
async def health_ready(response: Response):
    """Readiness probe: 200 so se podemos servir trafego."""
    db = await _check_database()
    anthropic = _check_anthropic_config()
    ready = db["status"] in ("ok", "skip") and anthropic["status"] in ("ok", "skip")
    if not ready:
        response.status_code = 503
    return {
        "ready": ready,
        "database": db["status"],
        "anthropic": anthropic["status"],
    }


@router.get("/logo-base64")
def logo_base64():
    return {"data_uri": LOGO_DATA_URI}
