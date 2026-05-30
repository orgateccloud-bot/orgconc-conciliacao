"""Audit middleware — registra mutacoes na tabela audit_log.

Intercepta apenas requests com 2xx em metodos mutadores (POST/PATCH/PUT/DELETE).
NUNCA falha o request: erros do audit caem em log mas o response chega ao cliente.
Body so eh lido se Content-Length <= AUDIT_BODY_LIMIT (default 64 KB).
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid

import jwt as _jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.core.config import DB_DISPONIVEL, SessionLocal

log = logging.getLogger("orgconc.audit")

# Rotas que NAO devem ser auditadas (ruido, health, polling)
_SKIP_PATHS_PREFIX = ("/health", "/auth/refresh", "/metrics", "/docs", "/openapi", "/v1/jobs")
_AUDIT_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
_AUDIT_BODY_LIMIT = int(os.environ.get("ORGCONC_AUDIT_BODY_LIMIT", str(64 * 1024)))

_ENTITY_FROM_PATH = {
    "/v1/clientes": "Cliente",
    "/v1/conciliar": "Conciliacao",
    "/v1/export": "Export",
    "/v1/jobs": "Job",
    "/v1/serpro": "SerproQuery",
    "/auth": "Auth",
}


def _entidade(path: str) -> str:
    for prefix, ent in _ENTITY_FROM_PATH.items():
        if path.startswith(prefix):
            return ent
    return "?"


def _acao(method: str, status: int) -> str:
    if method == "DELETE":
        return "delete"
    if method == "POST":
        return "create" if status == 201 else "action"
    if method in ("PATCH", "PUT"):
        return "update"
    return "other"


def _extrair_claims(request: Request) -> tuple[str, str]:
    """Retorna (sub, org_id). Anonymous se sem token."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        secret = os.environ.get("ORGCONC_JWT_SECRET", "")
        if secret:
            try:
                claims = _jwt.decode(
                    auth[7:],
                    secret,
                    algorithms=["HS256"],
                    options={"verify_exp": False},
                )
                return (
                    claims.get("sub", "anonymous"),
                    claims.get("org_id") or "00000000-0000-0000-0000-000000000001",
                )
            except Exception:
                pass
    return ("anonymous", "00000000-0000-0000-0000-000000000001")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Le body antes de despachar (se aplicavel) — body cache evita drain
        body_hash: str | None = None
        if (
            request.method in _AUDIT_METHODS
            and not any(request.url.path.startswith(p) for p in _SKIP_PATHS_PREFIX)
        ):
            try:
                cl = int(request.headers.get("content-length", "0") or "0")
            except ValueError:
                cl = 0
            if 0 < cl <= _AUDIT_BODY_LIMIT:
                body = await request.body()
                body_hash = hashlib.sha256(body).hexdigest()
                # Restaura o body para o handler poder ler de novo
                async def receive():
                    return {"type": "http.request", "body": body, "more_body": False}
                request._receive = receive  # type: ignore[attr-defined]

        response = await call_next(request)

        if (
            DB_DISPONIVEL
            and SessionLocal is not None
            and request.method in _AUDIT_METHODS
            and 200 <= response.status_code < 300
            and not any(request.url.path.startswith(p) for p in _SKIP_PATHS_PREFIX)
        ):
            try:
                await self._persistir(request, response, body_hash)
            except Exception:
                log.exception("audit_log persist failed")
        return response

    async def _persistir(self, request: Request, response: Response, body_hash: str | None) -> None:
        from api.db.models import AuditLog  # import local — evita ciclo
        sub, org = _extrair_claims(request)
        rid = request.headers.get("X-Request-ID", "-")
        async with SessionLocal() as db:
            entry = AuditLog(
                org_id=uuid.UUID(org),
                usuario_sub=sub,
                acao=_acao(request.method, response.status_code),
                entidade=_entidade(request.url.path),
                entidade_id=None,
                payload_hash=body_hash,
                ip=request.client.host if request.client else None,
                user_agent=(request.headers.get("user-agent") or "")[:512] or None,
                status_code=response.status_code,
                request_id=rid[:32] if rid else None,
            )
            db.add(entry)
            await db.commit()
