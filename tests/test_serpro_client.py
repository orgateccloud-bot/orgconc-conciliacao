"""Testes do scaffold SERPRO-ready (auth/transporte; Fase 1, IC-02).

Cobrem o que está implementado (gate de credenciais + fluxo OAuth2 de token com
httpx mockado). O mapeamento IC-02↔SERPRO é spec-pending e não é testado aqui.
"""
import pytest

from api.core import config
from api.services import serpro_client


class _FakeResp:
    def __init__(self, data, status=200):
        self._d = data
        self.status_code = status

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


class _FakeClient:
    """Fake do httpx.AsyncClient (async context manager) que devolve um token."""

    captured: dict = {}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, data=None, **k):
        _FakeClient.captured = {"url": url, "headers": headers or {}, "data": data}
        return _FakeResp({"access_token": "tok-123", "token_type": "Bearer", "expires_in": 3600})


def test_credenciais_ok_falso_sem_creds(monkeypatch):
    monkeypatch.setattr(config, "SERPRO_CONSUMER_KEY", "")
    monkeypatch.setattr(config, "SERPRO_CONSUMER_SECRET", "")
    assert serpro_client.credenciais_ok() is False


@pytest.mark.asyncio
async def test_obter_token_sem_creds_levanta_config_error(monkeypatch):
    monkeypatch.setattr(config, "SERPRO_CONSUMER_KEY", "")
    monkeypatch.setattr(config, "SERPRO_CONSUMER_SECRET", "")
    serpro_client._reset_token_cache()
    with pytest.raises(serpro_client.SerproConfigError):
        await serpro_client.obter_token()


@pytest.mark.asyncio
async def test_obter_token_fluxo_oauth(monkeypatch):
    monkeypatch.setattr(config, "SERPRO_CONSUMER_KEY", "ck")
    monkeypatch.setattr(config, "SERPRO_CONSUMER_SECRET", "cs")
    monkeypatch.setattr(serpro_client.httpx, "AsyncClient", _FakeClient)
    serpro_client._reset_token_cache()

    token = await serpro_client.obter_token()
    assert token == "tok-123"
    # Basic base64(ck:cs) no header + grant_type correto
    cap = _FakeClient.captured
    assert cap["headers"]["Authorization"].startswith("Basic ")
    assert cap["data"]["grant_type"] == "client_credentials"
    # 2ª chamada usa o cache (sem nova requisição precisaria de outro fake; aqui só
    # garantimos que retorna o mesmo token)
    assert await serpro_client.obter_token() == "tok-123"
