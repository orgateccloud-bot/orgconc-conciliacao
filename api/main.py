"""
API de Conciliacao Bancaria — ORGATEC OrgConc.

Execucao:
    uvicorn api.main:app --reload --port 8765
"""
from __future__ import annotations

import contextlib
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from api.core.config import (
    CORS_ORIGINS,
    DB_DISPONIVEL,
    MAX_UPLOAD_TOTAL_BYTES,
    MAX_UPLOAD_TOTAL_MB,
    REACT_DIST,
    ROOT_DIR,
    STATIC_DIR,
    _LOG_JSON,
    _LOG_LEVEL,
    _MODELOS_VALIDOS,
    engine,
    log,
)
from api.core.observability import init_sentry
from api.core.rate_limit import limiter
from api.core.templates import LOGO_DATA_URI
from api.routers import auth_routes, clientes, conciliacao, conciliacoes_list, exports, health, serpro
from api.services.logging_estruturado import RequestIdMiddleware, configurar_logging

# Re-export para testes e retrocompat
from api.parsers import (  # noqa: F401
    _chave_transacao,
    _classificar,
    _coletar_chaves_anomalas,
    _detectar_anomalias,
    _parse_arquivo,
    _parse_ofx,
    _parse_xml,
)
from api.services.excel import _gerar_xlsx  # noqa: F401
from api.services.db_persistence import salvar_no_banco as _salvar_no_banco  # noqa: F401
from api.services.render import render_html as _render_html  # noqa: F401
from api.services.storage import (  # noqa: F401
    carregar_dataset as _carregar_dataset,
    salvar_dataset as _salvar_dataset,
)

configurar_logging(nivel=_LOG_LEVEL, json_mode=_LOG_JSON)
init_sentry(release=os.environ.get("ORGCONC_RELEASE") or None)

_IS_HTTPS = os.environ.get("ORGCONC_ENV", "").strip().lower() in ("production", "prod") or \
            os.environ.get("ORGCONC_HTTPS_ENABLED", "").strip().lower() in ("1", "true", "yes")

_SENTRY_INGEST = "*.sentry.io" if os.environ.get("SENTRY_DSN", "").strip() else ""
_CONNECT_SRC = "connect-src 'self'" + (f" {_SENTRY_INGEST}" if _SENTRY_INGEST else "")
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
    "font-src 'self' fonts.gstatic.com; "
    "img-src 'self' data:; "
    f"{_CONNECT_SRC}; "
    "form-action 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "upgrade-insecure-requests"
)

_HSTS = "max-age=31536000; includeSubDomains; preload"


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next) -> StarletteResponse:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-XSS-Protection"] = "0"
        if _IS_HTTPS:
            response.headers["Strict-Transport-Security"] = _HSTS
        return response


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY nao configurada")
    if DB_DISPONIVEL:
        log.info("Banco configurado")
    else:
        log.info("Banco nao configurado — persistencia JSON local")
    yield
    if DB_DISPONIVEL and engine:
        await engine.dispose()


app = FastAPI(
    title="ORGATEC · Conciliacao Bancaria API",
    description="Cruza extratos OFX/PDF/XML. Gera HTML/XLSX/PDF.",
    version="0.5.0",
    lifespan=_lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(_SecurityHeadersMiddleware)

app.include_router(health.router)
app.include_router(auth_routes.router)
app.include_router(clientes.router)
app.include_router(serpro.router)
app.include_router(conciliacao.router)
app.include_router(exports.router)
app.include_router(conciliacoes_list.router)

# UI legada (periodo de transicao)
if STATIC_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui_legacy")

if REACT_DIST.exists():
    app.mount("/app", StaticFiles(directory=str(REACT_DIST), html=True), name="react_app")

@app.get("/deck", include_in_schema=False)
def frontend_legacy_redirect():
    """Dashboard HTML legado em frontend/."""
    html_path = ROOT_DIR / "frontend" / "index.html"
    if not html_path.exists():
        raise HTTPException(404, "Frontend nao encontrado")
    return FileResponse(str(html_path), media_type="text/html")

