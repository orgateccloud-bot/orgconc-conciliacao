"""Regressão do incidente 2026-06-10: o ping de DB não pode falhar em silêncio.

Produção rodou ~32h sem banco porque `_db_ping_sync` engolia a exceção
("password authentication failed" nunca apareceu em log algum). Estes testes
travam o contrato: cada tentativa loga warning com o tipo+1ª linha do erro, e
a falha final loga error — sem nunca incluir a URL/credencial.
"""
from __future__ import annotations

import logging

import psycopg2
import pytest

from api.core import config


@pytest.fixture()
def _ping_com_falha(monkeypatch):
    monkeypatch.setattr(config, "_DB_URL", "postgresql://app:segredo@db.exemplo:5432/x")
    monkeypatch.setattr("time.sleep", lambda s: None)  # sem backoff real no teste

    def _boom(*_a, **_k):
        raise psycopg2.OperationalError(
            'FATAL:  password authentication failed for user "app"\n'
            "connection to server at ... failed"
        )

    monkeypatch.setattr(psycopg2, "connect", _boom)


def test_ping_loga_warning_por_tentativa_e_error_final(_ping_com_falha, caplog):
    with caplog.at_level(logging.WARNING, logger="orgconc"):
        assert config._db_ping_sync(timeout_s=1) is False

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 3, "1 warning por tentativa (3 tentativas)"
    assert "OperationalError" in warnings[0].getMessage()
    assert "password authentication failed" in warnings[0].getMessage()
    # Só a 1ª linha do erro (as seguintes podem ecoar o DSN).
    assert "connection to server" not in warnings[0].getMessage()

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "SEM banco" in errors[0].getMessage()

    # Nunca vazar credencial/URL nos logs.
    tudo = " ".join(r.getMessage() for r in caplog.records)
    assert "segredo" not in tudo
    assert "postgresql://" not in tudo


def test_ping_sucesso_nao_loga_erro(monkeypatch, caplog):
    monkeypatch.setattr(config, "_DB_URL", "postgresql://app:segredo@db.exemplo:5432/x")

    class _Cur:
        def execute(self, *_a): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class _Conn:
        def cursor(self): return _Cur()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: _Conn())
    with caplog.at_level(logging.WARNING, logger="orgconc"):
        assert config._db_ping_sync(timeout_s=1) is True
    assert not caplog.records
