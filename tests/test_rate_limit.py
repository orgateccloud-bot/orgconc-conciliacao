"""Throttle real do rate-limiter (slowapi) — distinto do rate-limit do LLM.

P0 #3 do roadmap. `/auth/login` tem `@limiter.limit("10/minute")`; a 11a chamada
no mesmo minuto deve estourar 429, com headers de rate-limit (headers_enabled).
O reset autouse do conftest garante que cada teste comeca com o contador limpo.

Cobre tambem W3 (P0.5 + #26):
  - #13: em producao, REDIS_URL e obrigatorio (storage compartilhado entre
    workers/replicas). Sem ele, _validate_production_env() falha no startup.
  - #26: a key do rate-limit so usa o `sub` se o JWT for VALIDO (assinatura+exp).
    Token expirado cai para a chave por IP — nao consome a quota do user legitimo.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt as _jwt
import pytest
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


# ── #13 — REDIS_URL obrigatorio em producao (fail-fast no startup) ─────────

# Conjunto minimo de vars que satisfaz _validate_production_env, exceto REDIS_URL.
_PROD_ENV_BASE = {
    "ORGCONC_ENV": "production",
    "ORGCONC_JWT_SECRET": "x" * 32,
    "ORGCONC_ADMIN_EMAIL": "admin@orgatec.cloud",
    "ORGCONC_ADMIN_SENHA_HASH": "$2b$12$abcdefghijklmnopqrstuv",
    "ANTHROPIC_API_KEY": "sk-ant-test",
}


def test_producao_sem_redis_url_falha_no_startup():
    """Em prod, _validate_production_env deve levantar se REDIS_URL ausente."""
    from api.core import config

    env = dict(_PROD_ENV_BASE)
    env.pop("REDIS_URL", None)
    with patch.object(config, "_IS_PROD_ENV", True), \
            patch.dict(os.environ, env, clear=False):
        os.environ.pop("REDIS_URL", None)
        with pytest.raises(RuntimeError) as exc:
            config._validate_production_env()
    assert "REDIS_URL" in str(exc.value)


def test_producao_com_redis_url_nao_falha():
    """Com REDIS_URL (e demais vars) presente, a validacao passa."""
    from api.core import config

    env = dict(_PROD_ENV_BASE)
    env["REDIS_URL"] = "redis://localhost:6379/0"
    with patch.object(config, "_IS_PROD_ENV", True), \
            patch.dict(os.environ, env, clear=False):
        config._validate_production_env()  # nao deve levantar


def test_dev_sem_redis_url_nao_falha():
    """Em dev (nao-prod), REDIS_URL e opcional — in-memory permitido."""
    from api.core import config

    with patch.object(config, "_IS_PROD_ENV", False), \
            patch.dict(os.environ, {}, clear=False):
        os.environ.pop("REDIS_URL", None)
        config._validate_production_env()  # nao deve levantar


# ── #26 — token expirado nao consome a quota do sub (cai para IP) ──────────

def _make_token(secret: str, sub: str, *, expira_em_min: int) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iat": int((agora - timedelta(minutes=60)).timestamp()),
        "exp": int((agora + timedelta(minutes=expira_em_min)).timestamp()),
    }
    return _jwt.encode(payload, secret, algorithm="HS256")


def test_token_valido_usa_chave_por_sub():
    from api.core import rate_limit

    secret = "s" * 32
    token = _make_token(secret, "user-legitimo", expira_em_min=60)
    req = _fake_request(f"Bearer {token}")
    with patch.dict(os.environ, {"ORGCONC_JWT_SECRET": secret}):
        assert rate_limit._get_rate_key(req) == "sub:user-legitimo"


def test_token_expirado_cai_para_ip():
    """Token vencido NAO deve mapear para sub: — isolaria o abuso no user real."""
    from api.core import rate_limit

    secret = "s" * 32
    token = _make_token(secret, "user-legitimo", expira_em_min=-1)  # ja expirado
    req = _fake_request(f"Bearer {token}", client_host="203.0.113.9")
    with patch.dict(os.environ, {"ORGCONC_JWT_SECRET": secret}):
        chave = rate_limit._get_rate_key(req)
    assert chave != "sub:user-legitimo"
    assert chave == "203.0.113.9"


def test_token_assinatura_invalida_cai_para_ip():
    from api.core import rate_limit

    token = _make_token("outro-segredo-qualquer-com-32-chars!!", "x", expira_em_min=60)
    req = _fake_request(f"Bearer {token}", client_host="198.51.100.7")
    with patch.dict(os.environ, {"ORGCONC_JWT_SECRET": "s" * 32}):
        assert rate_limit._get_rate_key(req) == "198.51.100.7"


class _FakeClient:
    def __init__(self, host: str):
        self.host = host


class _FakeRequest:
    """Stub minimo de starlette.Request para _get_rate_key (le headers + client)."""

    def __init__(self, auth: str, client_host: str):
        self.headers = {"Authorization": auth} if auth else {}
        self.client = _FakeClient(client_host)


def _fake_request(auth: str, client_host: str = "127.0.0.1") -> _FakeRequest:
    return _FakeRequest(auth, client_host)
