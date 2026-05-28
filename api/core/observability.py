"""Inicializacao do Sentry com PII masking e correlacao por request_id.

Inicializa Sentry apenas se SENTRY_DSN estiver definido. Reusa o mesmo
mask_pii() do logging estruturado para nao vazar CPF/CNPJ/email/IP em
eventos enviados ao Sentry.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from api.services.logging_estruturado import mask_pii, request_id_var

log = logging.getLogger("orgconc.observability")

_SENSITIVE_KEYS = {
    "password", "senha", "token", "authorization", "auth", "cookie",
    "api_key", "apikey", "secret", "x-api-key",
}


def _scrub_dict(d: Any) -> Any:
    """Mascara strings e oculta valores em chaves sensiveis."""
    if isinstance(d, dict):
        return {
            k: ("***" if k.lower() in _SENSITIVE_KEYS else _scrub_dict(v))
            for k, v in d.items()
        }
    if isinstance(d, (list, tuple)):
        scrubbed = [_scrub_dict(v) for v in d]
        return type(d)(scrubbed) if isinstance(d, tuple) else scrubbed
    if isinstance(d, str):
        return mask_pii(d)
    return d


def _before_send(event: dict, _hint: dict) -> Optional[dict]:
    """Hook do Sentry: anexa request_id e remove PII antes do envio."""
    try:
        rid = request_id_var.get()
        if rid and rid != "-":
            event.setdefault("tags", {})["request_id"] = rid
        if "request" in event:
            event["request"] = _scrub_dict(event["request"])
        if "extra" in event:
            event["extra"] = _scrub_dict(event["extra"])
        if "exception" in event and isinstance(event["exception"], dict):
            for entry in event["exception"].get("values", []):
                if "value" in entry and isinstance(entry["value"], str):
                    entry["value"] = mask_pii(entry["value"])
        if "message" in event and isinstance(event["message"], str):
            event["message"] = mask_pii(event["message"])
    except Exception:
        log.exception("Falha em before_send do Sentry — evento descartado")
        return None
    return event


def _resolver_sample_rate() -> float:
    raw = os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "").strip()
    if raw:
        try:
            return max(0.0, min(1.0, float(raw)))
        except ValueError:
            pass
    env = os.environ.get("ORGCONC_ENV", "").strip().lower()
    return 0.1 if env in ("production", "prod") else 1.0


def _resolver_environment() -> str:
    return (
        os.environ.get("SENTRY_ENVIRONMENT", "").strip()
        or os.environ.get("ORGCONC_ENV", "").strip()
        or "development"
    )


def init_sentry(release: Optional[str] = None) -> bool:
    """Inicializa Sentry se SENTRY_DSN estiver definido. Retorna True se ativou."""
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        log.warning("SENTRY_DSN definido mas sentry-sdk nao instalado — pulando init")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=_resolver_environment(),
        release=release,
        traces_sample_rate=_resolver_sample_rate(),
        send_default_pii=False,
        max_breadcrumbs=50,
        before_send=_before_send,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    log.info("sentry_inicializado", extra={"environment": _resolver_environment()})
    return True
