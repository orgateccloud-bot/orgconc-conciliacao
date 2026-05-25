"""Testes para api/core/observability.py — Sentry init e PII scrubbing."""
from __future__ import annotations

import os

import pytest

from api.core import observability
from api.services.logging_estruturado import request_id_var


@pytest.fixture(autouse=True)
def _limpa_env():
    keys = ["SENTRY_DSN", "SENTRY_TRACES_SAMPLE_RATE", "SENTRY_ENVIRONMENT", "ORGCONC_ENV"]
    saved = {k: os.environ.pop(k, None) for k in keys}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


def test_init_sentry_sem_dsn_retorna_false():
    assert observability.init_sentry() is False


def test_init_sentry_sem_sdk_instalado(monkeypatch):
    os.environ["SENTRY_DSN"] = "https://x@sentry.io/1"
    # Simula import error
    import sys
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    assert observability.init_sentry() is False


def test_scrub_dict_mascara_chaves_sensiveis():
    raw = {
        "password": "minhasenha123",
        "Authorization": "Bearer xyz",
        "user": "joao@example.com",
        "nested": {"api_key": "sk-abc", "ok": "valor"},
    }
    out = observability._scrub_dict(raw)
    assert out["password"] == "***"
    assert out["Authorization"] == "***"
    assert "@" in out["user"]  # nao oculta, mas mascara via PII
    assert out["nested"]["api_key"] == "***"
    assert out["nested"]["ok"] == "valor"


def test_scrub_dict_mascara_cpf_em_string():
    raw = {"detalhe": "CPF do cliente: 123.456.789-00"}
    out = observability._scrub_dict(raw)
    assert "123.456.789-00" not in out["detalhe"]
    assert "***" in out["detalhe"]


def test_before_send_anexa_request_id():
    token = request_id_var.set("abc123def456")
    try:
        event = {"message": "erro generico"}
        out = observability._before_send(event, {})
    finally:
        request_id_var.reset(token)
    assert out is not None
    assert out["tags"]["request_id"] == "abc123def456"


def test_before_send_mascara_pii_em_message():
    event = {"message": "Falha para cliente CPF 999.888.777-66"}
    out = observability._before_send(event, {})
    assert out is not None
    assert "999.888.777-66" not in out["message"]


def test_before_send_mascara_email_em_exception_value():
    event = {
        "exception": {
            "values": [
                {"type": "ValueError", "value": "email invalido: usuario@exemplo.com"}
            ]
        }
    }
    out = observability._before_send(event, {})
    assert out is not None
    val = out["exception"]["values"][0]["value"]
    assert "usuario@exemplo.com" not in val


def test_before_send_scrub_em_request_extra():
    event = {
        "request": {"headers": {"Authorization": "Bearer secreto"}},
        "extra": {"senha": "123456"},
    }
    out = observability._before_send(event, {})
    assert out["request"]["headers"]["Authorization"] == "***"
    assert out["extra"]["senha"] == "***"


def test_before_send_nao_quebra_sem_request_id():
    # default do contextvar é "-"
    event = {"message": "ok"}
    out = observability._before_send(event, {})
    assert out is not None
    # sem request_id real, nao adiciona tag
    assert "tags" not in out or out["tags"].get("request_id") != "-"


def test_resolver_sample_rate_default_prod_eh_baixo():
    os.environ["ORGCONC_ENV"] = "production"
    assert observability._resolver_sample_rate() == 0.1


def test_resolver_sample_rate_default_dev_eh_alto():
    os.environ["ORGCONC_ENV"] = "development"
    assert observability._resolver_sample_rate() == 1.0


def test_resolver_sample_rate_override_env():
    os.environ["SENTRY_TRACES_SAMPLE_RATE"] = "0.5"
    assert observability._resolver_sample_rate() == 0.5


def test_resolver_sample_rate_clamp_valores():
    os.environ["SENTRY_TRACES_SAMPLE_RATE"] = "2.5"
    assert observability._resolver_sample_rate() == 1.0
    os.environ["SENTRY_TRACES_SAMPLE_RATE"] = "-0.5"
    assert observability._resolver_sample_rate() == 0.0


def test_resolver_environment_fallback_orgconc_env():
    os.environ["ORGCONC_ENV"] = "staging"
    assert observability._resolver_environment() == "staging"


def test_resolver_environment_default_dev():
    assert observability._resolver_environment() == "development"
