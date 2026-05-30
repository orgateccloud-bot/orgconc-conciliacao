"""Exception handlers no formato RFC 7807 (application/problem+json).

Cobertura:
- HTTPException     (FastAPI) -> 4xx/5xx tipados
- RequestValidationError      -> 422 com lista de field errors
- DomainError                 -> 400 (RegraViolada/ValorInvalido) ou 404
- Exception (qualquer)        -> 500 generico (NAO vaza traceback)

Body:
{
  "type":       "https://orgconc.app/errors/<status>",
  "title":      "<descricao curta>",
  "status":     <code>,
  "detail":     "<mensagem ou dict>",
  "instance":   "<request path>",
  "request_id": "<correlation id>",
  "errors":     [...] (opcional, so para 422)
}
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.domain.exceptions import (
    DomainError,
    EntidadeNaoEncontrada,
    FormatoNaoSuportado,
    RegraViolada,
    ValorInvalido,
)

log = logging.getLogger("orgconc.errors")

_ERROR_BASE = "https://orgconc.app/errors"


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", "-")


def _problem(
    *,
    request: Request,
    status: int,
    title: str,
    detail: Any = None,
    extras: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{_ERROR_BASE}/{status}",
        "title": title,
        "status": status,
        "instance": request.url.path,
        "request_id": _request_id(request),
    }
    if detail is not None:
        body["detail"] = detail
    if extras:
        body.update(extras)
    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )


# ── Handlers ────────────────────────────────────────────────────────────────

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Mapeia HTTPException → Problem Details."""
    title = _DEFAULT_TITLES.get(exc.status_code, "Error")
    # FastAPI pode levantar HTTPException com `detail` dict (e.g. {"anthropic_error": "..."})
    return _problem(request=request, status=exc.status_code, title=title, detail=exc.detail)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422 com a lista normalizada de erros do Pydantic."""
    errors = []
    for err in exc.errors():
        errors.append({
            "loc": ".".join(str(x) for x in err.get("loc", [])),
            "msg": err.get("msg"),
            "type": err.get("type"),
        })
    return _problem(
        request=request,
        status=422,
        title="Validation failed",
        detail="Payload invalido. Veja 'errors' para detalhes.",
        extras={"errors": errors},
    )


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Mapeia erros de dominio para 4xx adequados."""
    if isinstance(exc, EntidadeNaoEncontrada):
        return _problem(request=request, status=404, title="Not Found", detail=str(exc))
    if isinstance(exc, (ValorInvalido, FormatoNaoSuportado)):
        return _problem(request=request, status=400, title="Bad Request", detail=str(exc))
    if isinstance(exc, RegraViolada):
        msg = str(exc).lower()
        if "ja cadastrado" in msg or "duplicat" in msg or "conflict" in msg:
            return _problem(request=request, status=409, title="Conflict", detail=str(exc))
        return _problem(request=request, status=400, title="Business rule violation", detail=str(exc))
    # DomainError generico
    return _problem(request=request, status=400, title="Bad Request", detail=str(exc))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """500 generico. Loga stacktrace; nao vaza para cliente."""
    log.exception("unhandled_exception", extra={"path": request.url.path})
    return _problem(
        request=request,
        status=500,
        title="Internal Server Error",
        detail="Erro inesperado. Equipe foi notificada.",
    )


# ── Tabela de titulos padrao por status ────────────────────────────────────

_DEFAULT_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    413: "Payload Too Large",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
}


def registrar_handlers(app) -> None:
    """Chamado pelo main.py — registra todos os handlers no FastAPI."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
