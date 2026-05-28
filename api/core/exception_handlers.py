"""Exception handlers globais — formato JSON uniforme com request_id."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.services.logging_estruturado import request_id_var

log = logging.getLogger("orgconc.errors")

_IS_PROD = os.environ.get("ORGCONC_ENV", "").strip().lower() in ("production", "prod")


async def _handler_500(request: Request, exc: Exception) -> JSONResponse:
    """Retorna 500 JSON estruturado, sem vazar detalhes em producao."""
    rid = request_id_var.get()
    log.exception(
        "erro_nao_tratado",
        extra={"path": request.url.path, "method": request.method, "request_id": rid},
    )
    detalhe = "Erro interno" if _IS_PROD else f"{type(exc).__name__}: {exc}"
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": detalhe, "request_id": rid},
        headers={"X-Request-ID": rid} if rid and rid != "-" else None,
    )


def registrar_handlers(app: FastAPI) -> None:
    """Anexa o handler 500 global no app."""
    app.add_exception_handler(Exception, _handler_500)
