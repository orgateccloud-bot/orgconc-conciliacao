"""Bootstrap do FastAPI: middlewares, CSP/HSTS, lifespan, CORS.

Extraido de api/main.py para reduzir o god file e facilitar testes.
"""
from __future__ import annotations

import contextlib
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from api.core import config as _config
from api.core.config import CORS_ORIGINS, engine, log, verificar_db_disponivel
from api.core.exception_handlers import registrar_handlers
from api.core.prometheus_metrics import PrometheusMiddleware
from api.core.rate_limit import limiter, rate_limit_exceeded_handler
from api.services.logging_estruturado import RequestIdMiddleware


def _is_https() -> bool:
    return (
        os.environ.get("ORGCONC_ENV", "").strip().lower() in ("production", "prod")
        or os.environ.get("ORGCONC_HTTPS_ENABLED", "").strip().lower() in ("1", "true", "yes")
    )


def _build_csp() -> str:
    sentry_active = bool(os.environ.get("SENTRY_DSN", "").strip())
    connect_src = "connect-src 'self'" + (" *.sentry.io" if sentry_active else "")
    return (
        "default-src 'self'; "
        "script-src 'self' cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
        "font-src 'self' fonts.gstatic.com; "
        "img-src 'self' data:; "
        f"{connect_src}; "
        "form-action 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "upgrade-insecure-requests"
    )


_HSTS = "max-age=31536000; includeSubDomains; preload"


class BodyLimitMiddleware(BaseHTTPMiddleware):
    """Rejeita requests cujo Content-Length excede o limite (413).

    Le o limite live de config._MAX_BODY_BYTES para que testes possam ajustar
    o teto sem reiniciar a app.
    """

    async def dispatch(self, request: StarletteRequest, call_next) -> StarletteResponse:
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > _config._MAX_BODY_BYTES:
                    return StarletteResponse(
                        content='{"detail":"Corpo da requisicao excede o limite"}',
                        status_code=413,
                        media_type="application/json",
                    )
            except ValueError:
                pass
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Aplica headers de seguranca (CSP, HSTS, COOP, etc.) em toda resposta."""

    def __init__(self, app, csp: str | None = None, https: bool = False) -> None:
        super().__init__(app)
        self._csp = csp or _build_csp()
        self._https = https

    async def dispatch(self, request: StarletteRequest, call_next) -> StarletteResponse:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = self._csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-XSS-Protection"] = "0"
        if self._https:
            response.headers["Strict-Transport-Security"] = _HSTS
        # Respostas sensiveis (tokens, relatorios financeiros) nunca devem ser
        # cacheadas por proxies ou browser. Cobre tambem respostas de erro.
        if request.url.path.startswith(("/auth/", "/export/")):
            response.headers["Cache-Control"] = "no-store"
        return response


class RLSContextMiddleware:
    """Popula o contexto de org (RLS) por request a partir do JWT.

    Middleware ASGI puro (não BaseHTTPMiddleware) para garantir que o ContextVar
    setado aqui propague ao endpoint e às chamadas de banco no MESMO contexto.
    Extrai o token do header Authorization ou do cookie `orgconc_token`, decodifica
    best-effort (token ausente/inválido → sem org) e seta `app.org_id` via
    set_org_context. O listener `after_begin` (api/db/rls_context) aplica o
    `SET LOCAL` em cada transação. Inócuo enquanto a conexão for `postgres`.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        from api.db.rls_context import (
            reset_org_context,
            reset_superadmin_context,
            set_org_context,
            set_superadmin_context,
        )

        org_id, superadmin = _ctx_do_scope(scope)
        t_org = set_org_context(org_id)
        t_super = set_superadmin_context(superadmin)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_superadmin_context(t_super)
            reset_org_context(t_org)


def _ctx_do_scope(scope) -> tuple[str | None, bool]:
    """(org_id, superadmin) do JWT no request (header Bearer ou cookie); best-effort.

    Token ausente/inválido/expirado → (None, False). O claim `superadmin` só é
    emitido no login do admin por env (api/routers/auth_routes), nunca p/ usuário comum.
    """
    try:
        headers = {
            k.decode("latin1").lower(): v.decode("latin1")
            for k, v in (scope.get("headers") or [])
        }
        jwt = None
        auth = headers.get("authorization")
        if auth:
            jwt = auth[7:].strip() if auth.lower().startswith("bearer ") else auth.strip()
        if not jwt:
            for part in headers.get("cookie", "").split(";"):
                name, _, val = part.strip().partition("=")
                if name == "orgconc_token":
                    jwt = val.strip()
                    break
        if not jwt:
            return None, False
        from api.services.auth import decodificar_token

        claims = decodificar_token(jwt)
        return claims.org_id, bool(claims.superadmin)
    except Exception:  # noqa: BLE001 — token ausente/inválido/expirado → sem contexto
        return None, False


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY nao configurada")
    # Resolve o modelo mais recente de cada familia via Models API (best-effort).
    _config.atualizar_modelos()
    # Ping do DB movido para startup (era feito em import-time e bloqueava ate 14s)
    db_ok = verificar_db_disponivel()
    if db_ok:
        log.info("Banco configurado")
    else:
        log.info("Banco nao configurado — persistencia JSON local")
    yield
    if _config.DB_DISPONIVEL and engine:
        await engine.dispose()


def criar_app(
    title: str = "ORGATEC · Conciliacao Bancaria API",
    description: str = "Cruza extratos OFX/PDF/XML. Gera HTML/XLSX/PDF.",
    version: str = "0.5.0",
) -> FastAPI:
    """Cria o FastAPI com todos os middlewares + handlers configurados."""
    # Em producao, desabilita Swagger/ReDoc/OpenAPI — nao expor o mapa de
    # endpoints fiscais e de auditoria publicamente.
    _is_prod = os.environ.get("ORGCONC_ENV", "").strip().lower() in ("production", "prod")
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan,
        docs_url=None if _is_prod else "/docs",
        redoc_url=None if _is_prod else "/redoc",
        openapi_url=None if _is_prod else "/openapi.json",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(RequestIdMiddleware)
    # Contexto de RLS por org (a partir do JWT). No-op até o flip para app_orgconc.
    app.add_middleware(RLSContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(SecurityHeadersMiddleware, https=_is_https())
    app.add_middleware(BodyLimitMiddleware)
    registrar_handlers(app)
    return app
