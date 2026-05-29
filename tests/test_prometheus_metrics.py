"""Testes da instrumentação Prometheus (middleware + endpoint /metrics)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.core.prometheus_metrics import (
    PrometheusMiddleware,
    metrics_endpoint,
)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return metrics_endpoint()

    return app


def test_metrics_endpoint_exposto_em_formato_prometheus():
    client = TestClient(_app())
    res = client.get("/metrics")
    assert res.status_code in (200, 503)
    if res.status_code == 200:
        assert "text/plain" in res.headers["content-type"]


def test_requisicao_incrementa_contador():
    client = TestClient(_app())
    client.get("/ping")
    res = client.get("/metrics")
    if res.status_code == 503:
        # prometheus_client nao instalado — nada a verificar
        return
    body = res.text
    assert "orgconc_http_requests_total" in body
    # a rota /ping deve aparecer com status 200
    assert "/ping" in body


def test_latencia_observada():
    client = TestClient(_app())
    client.get("/ping")
    res = client.get("/metrics")
    if res.status_code == 503:
        return
    assert "orgconc_http_request_duration_seconds" in res.text


def test_endpoint_metrics_nao_e_contado_a_si_mesmo():
    client = TestClient(_app())
    res = client.get("/metrics")
    if res.status_code == 503:
        return
    # O proprio /metrics nao deve gerar serie com path="/metrics"
    assert 'path="/metrics"' not in res.text
