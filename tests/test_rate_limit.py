"""Throttle real do rate-limiter (slowapi) — distinto do rate-limit do LLM.

P0 #3 do roadmap. `/auth/login` tem `@limiter.limit("10/minute")`; a 11a chamada
no mesmo minuto deve estourar 429, com headers de rate-limit (headers_enabled).
O reset autouse do conftest garante que cada teste comeca com o contador limpo.
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

_CRED = {"email": "x@y.com", "senha": "12345678"}


def test_login_excede_limite_retorna_429():
    statuses = [
        client.post("/auth/login", json=_CRED).status_code for _ in range(11)
    ]
    assert statuses[-1] == 429, statuses            # a 11a estoura
    assert 429 not in statuses[:10], statuses        # as 10 primeiras nao estouram


def test_resposta_429_tem_headers_de_rate_limit():
    resp = None
    for _ in range(12):
        resp = client.post("/auth/login", json=_CRED)
        if resp.status_code == 429:
            break
    assert resp is not None and resp.status_code == 429
    headers = {k.lower() for k in resp.headers}
    assert "retry-after" in headers, dict(resp.headers)
    assert "x-ratelimit-limit" in headers, dict(resp.headers)
