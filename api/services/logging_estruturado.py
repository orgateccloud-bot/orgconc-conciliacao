"""Logging estruturado JSON com request_id por requisicao.

Exporta:
- JsonFormatter: formatter que serializa registros em JSON compacto
- request_id_var: contextvar com o ID da requisicao corrente
- RequestIdMiddleware: middleware que injeta X-Request-ID nos headers
- configurar_logging(): ativa o stack na startup
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class JsonFormatter(logging.Formatter):
    """Formatter que serializa LogRecord como JSON compacto.

    Campos: ts, lvl, msg, logger, request_id e quaisquer `extra` passados.
    """

    _RESERVADOS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Campos extras (passados via log.info("...", extra={"chave": valor}))
        for k, v in record.__dict__.items():
            if k not in self._RESERVADOS and not k.startswith("_"):
                try:
                    json.dumps(v)
                    payload[k] = v
                except TypeError:
                    payload[k] = repr(v)
        return json.dumps(payload, ensure_ascii=False)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Gera/propaga X-Request-ID e armazena no contextvar.

    Loga inicio + fim de cada requisicao (latencia + status).
    """

    def __init__(self, app, logger_name: str = "orgconc.http") -> None:
        super().__init__(app)
        self.log = logging.getLogger(logger_name)

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        inicio = time.perf_counter()
        try:
            response = await call_next(request)
            dur_ms = round((time.perf_counter() - inicio) * 1000, 1)
            self.log.info(
                "http_request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duracao_ms": dur_ms,
                    "client": request.client.host if request.client else None,
                },
            )
            response.headers["X-Request-ID"] = rid
            return response
        except Exception:
            dur_ms = round((time.perf_counter() - inicio) * 1000, 1)
            self.log.exception(
                "http_error",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duracao_ms": dur_ms,
                },
            )
            raise
        finally:
            request_id_var.reset(token)


def configurar_logging(nivel: str = "INFO", json_mode: bool = True) -> None:
    """Configura logging global (root + orgconc) em modo JSON ou texto.

    json_mode=False eh util em dev local para output legivel.
    """
    handler = logging.StreamHandler(sys.stdout)
    if json_mode:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s [%(message)s]"
        ))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, nivel.upper(), logging.INFO))

    # Reduz verbosidade de libs muito barulhentas
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
