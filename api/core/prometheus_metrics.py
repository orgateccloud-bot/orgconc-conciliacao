"""Métricas Prometheus — instrumentação HTTP opcional.

Exposto em GET /metrics. Se prometheus_client não estiver instalado, o
middleware vira no-op e o endpoint responde 503, sem quebrar a aplicação.

Métricas expostas:
    orgconc_http_requests_total{method,path,status}   — contador
    orgconc_http_request_duration_seconds{method,path} — histograma de latência
    orgconc_http_requests_in_progress                  — gauge de requests ativos
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _PROMETHEUS_OK = True
except ImportError:  # pragma: no cover — lib opcional
    _PROMETHEUS_OK = False
    CONTENT_TYPE_LATEST = "text/plain"


if _PROMETHEUS_OK:
    _REQUESTS = Counter(
        "orgconc_http_requests_total",
        "Total de requisições HTTP processadas",
        ["method", "path", "status"],
    )
    _LATENCY = Histogram(
        "orgconc_http_request_duration_seconds",
        "Latência das requisições HTTP em segundos",
        ["method", "path"],
    )
    _IN_PROGRESS = Gauge(
        "orgconc_http_requests_in_progress",
        "Requisições HTTP em andamento",
    )


def _rota_template(request: Request) -> str:
    """Usa o template da rota (/clientes/{id}) em vez do path concreto.

    Evita explosão de cardinalidade no Prometheus por IDs únicos.
    """
    rota = request.scope.get("route")
    if rota is not None and getattr(rota, "path", None):
        return rota.path
    return request.url.path


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Mede contagem, latência e concorrência de cada requisição."""

    async def dispatch(self, request: Request, call_next):
        if not _PROMETHEUS_OK:
            return await call_next(request)

        if request.url.path == "/metrics":
            return await call_next(request)

        _IN_PROGRESS.inc()
        inicio = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - inicio
            path = _rota_template(request)
            _IN_PROGRESS.dec()
            _LATENCY.labels(request.method, path).observe(elapsed)
            _REQUESTS.labels(request.method, path, str(status)).inc()


def metrics_endpoint() -> Response:
    """Resposta para GET /metrics no formato de exposição do Prometheus."""
    if not _PROMETHEUS_OK:
        return Response(
            "prometheus_client nao instalado",
            status_code=503,
            media_type="text/plain",
        )
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
