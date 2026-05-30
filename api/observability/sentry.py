"""Inicializacao Sentry — backend.

Integrado com PII masking de `api/services/logging_estruturado.py`:
o before_send mascara CPF/CNPJ/email/IP em strings dos eventos.
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("orgconc.sentry")


def _mask_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Mascara PII em mensagens/exceptions/breadcrumbs antes de enviar."""
    from api.services.logging_estruturado import mask_pii

    def walk(node: Any) -> Any:
        if isinstance(node, str):
            return mask_pii(node)
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(event)


def init_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        log.info("SENTRY_DSN nao configurado — Sentry desativado")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        log.warning("sentry-sdk nao instalado — pip install sentry-sdk[fastapi]")
        return

    env = os.environ.get("ORGCONC_ENV", "development").strip().lower()
    sample_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    release = os.environ.get("SENTRY_RELEASE") or _read_version()

    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        release=release,
        traces_sample_rate=sample_rate,
        send_default_pii=False,
        attach_stacktrace=True,
        before_send=_mask_event,
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
            SqlalchemyIntegration(),
        ],
    )
    log.info("Sentry inicializado (env=%s release=%s sample=%s)", env, release, sample_rate)


def _read_version() -> str | None:
    try:
        from api.core.config import VERSION
        return VERSION
    except Exception:
        return None
