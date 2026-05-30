"""Metricas Prometheus + middleware de instrumentacao HTTP."""
from __future__ import annotations

import logging
import time

from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.multiprocess import MultiProcessCollector
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

log = logging.getLogger("orgconc.metrics")

# Registry default (in-process). Para multi-process workers, configurar
# PROMETHEUS_MULTIPROC_DIR e usar MultiProcessCollector — feito em metrics_response().

http_requests_total = Counter(
    "orgconc_http_requests_total",
    "Total de requisicoes HTTP recebidas",
    ["method", "route", "status"],
)

http_request_duration_seconds = Histogram(
    "orgconc_http_request_duration_seconds",
    "Latencia das requisicoes HTTP",
    ["method", "route"],
    buckets=(0.005, 0.025, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 90.0),
)

llm_call_seconds = Histogram(
    "orgconc_llm_call_seconds",
    "Latencia de chamadas ao LLM",
    ["modelo", "status"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 90.0),
)

conciliacao_total = Counter(
    "orgconc_conciliacao_total",
    "Total de conciliacoes processadas",
    ["modo", "status"],
)

db_pool_size = Gauge(
    "orgconc_db_pool_size",
    "Tamanho atual do pool SQLAlchemy",
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Conta cada request HTTP em http_requests_total + duracao."""

    async def dispatch(self, request: Request, call_next) -> StarletteResponse:
        # Resolve route template para evitar cardinalidade explosiva
        # (sem isso /v1/clientes/<uuid> vira N labels distintos)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            route_template = self._route_template(request)
            dur = time.perf_counter() - t0
            http_requests_total.labels(
                method=request.method, route=route_template, status=str(status)
            ).inc()
            http_request_duration_seconds.labels(
                method=request.method, route=route_template
            ).observe(dur)
        return response

    @staticmethod
    def _route_template(request: Request) -> str:
        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            return route.path
        return request.url.path


def metrics_response() -> Response:
    """Endpoint /metrics — formato Prometheus."""
    import os
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        registry = CollectorRegistry()
        MultiProcessCollector(registry)
        data = generate_latest(registry)
    else:
        data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
