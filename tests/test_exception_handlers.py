"""Testes do exception handler global 500."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.core.exception_handlers import registrar_handlers
from api.services.logging_estruturado import RequestIdMiddleware


def _app_com_endpoint_que_explode(monkeypatch=None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    registrar_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    return app


def test_500_retorna_json_estruturado_em_dev(monkeypatch):
    monkeypatch.delenv("ORGCONC_ENV", raising=False)
    # Re-importa para recalcular _IS_PROD
    import importlib
    from api.core import exception_handlers
    importlib.reload(exception_handlers)
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    exception_handlers.registrar_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("detalhe-sensivel")

    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/boom")
    assert res.status_code == 500
    body = res.json()
    assert body["error"] == "internal_server_error"
    assert "RuntimeError" in body["detail"]
    assert "detalhe-sensivel" in body["detail"]
    assert "request_id" in body


def test_500_omite_detalhes_em_producao(monkeypatch):
    monkeypatch.setenv("ORGCONC_ENV", "production")
    import importlib
    from api.core import exception_handlers
    importlib.reload(exception_handlers)
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    exception_handlers.registrar_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("detalhe-super-sensivel")

    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/boom")
    assert res.status_code == 500
    body = res.json()
    assert body["detail"] == "Erro interno"
    assert "detalhe-super-sensivel" not in body["detail"]
    # Limpa para nao afetar outros testes
    monkeypatch.delenv("ORGCONC_ENV", raising=False)
    importlib.reload(exception_handlers)
