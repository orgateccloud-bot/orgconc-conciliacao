"""Testes diretos do código de segurança dos commits a362af48/3c14dde9.

Cobre o que até então só tinha cobertura indireta:
- BodyLimitMiddleware (411 sem Content-Length, 400 malformado, 413 acima do teto)
- /metrics protegido por ORGCONC_METRICS_TOKEN (fechado em produção sem token)
- SecurityHeadersMiddleware (CSP/COOP/CORP + Cache-Control em rotas sensíveis)
- escopo_cliente_listagem (ponto único do filtro de tenant em listagens)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("ORGCONC_DATA_DIR", str(Path(__file__).resolve().parent / "_data_test"))
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.main import app  # noqa: E402

client = TestClient(app)


# ── BodyLimitMiddleware ──────────────────────────────────────────────────────

def test_body_limit_post_sem_content_length_retorna_411():
    """POST com Transfer-Encoding: chunked (sem Content-Length) não pode
    contornar o limite de corpo — o middleware nega com 411 Length Required."""
    # content como gerador força o httpx a usar chunked (sem Content-Length)
    r = client.post("/health", content=iter([b"pedaco-1", b"pedaco-2"]))
    assert r.status_code == 411
    assert "Content-Length" in r.json()["detail"]


def test_body_limit_content_length_malformado_retorna_400():
    """Content-Length não numérico é request malformado → 400 (antes era
    silenciosamente ignorado, abrindo bypass)."""
    r = client.get("/health", headers={"Content-Length": "nao-e-numero"})
    assert r.status_code == 400


def test_body_limit_acima_do_teto_retorna_413():
    """Corpo declarado acima de config._MAX_BODY_BYTES → 413 (lido live,
    como documentado no middleware)."""
    import api.core.config as config

    with patch.object(config, "_MAX_BODY_BYTES", 10):
        r = client.post("/health", content=b"x" * 100)
    assert r.status_code == 413
    assert "limite" in r.json()["detail"].lower()


def test_body_limit_get_sem_content_length_passa():
    """GET sem corpo (sem Content-Length) não é afetado pelo 411 — o
    requisito só vale para métodos com corpo (POST/PUT/PATCH)."""
    r = client.get("/health")
    assert r.status_code == 200


def test_body_limit_post_com_content_length_normal_passa():
    """POST com Content-Length dentro do teto atravessa o middleware
    (405 do /health prova que chegou ao roteamento, não foi barrado)."""
    r = client.post("/health", content=b"ok")
    assert r.status_code not in (400, 411, 413)


# ── /metrics protegido (ORGCONC_METRICS_TOKEN) ───────────────────────────────

def test_metrics_com_token_configurado_sem_authorization_retorna_404():
    """Com token configurado, request sem Authorization não revela nem a
    existência do endpoint (404, não 401/403)."""
    with patch.dict(os.environ, {"ORGCONC_METRICS_TOKEN": "tok-secreto-123"}):
        r = client.get("/metrics")
    assert r.status_code == 404


def test_metrics_com_bearer_correto_retorna_200():
    """Scraper autenticado (Authorization: Bearer <token>) recebe as métricas."""
    with patch.dict(os.environ, {"ORGCONC_METRICS_TOKEN": "tok-secreto-123"}):
        r = client.get("/metrics", headers={"Authorization": "Bearer tok-secreto-123"})
    assert r.status_code == 200
    assert "orgconc_http_requests_total" in r.text


def test_metrics_com_bearer_errado_retorna_404():
    with patch.dict(os.environ, {"ORGCONC_METRICS_TOKEN": "tok-secreto-123"}):
        r = client.get("/metrics", headers={"Authorization": "Bearer token-errado"})
    assert r.status_code == 404


def test_metrics_em_producao_sem_token_configurado_retorna_404():
    """Fail-closed: produção sem ORGCONC_METRICS_TOKEN definido = endpoint
    fechado (404), nunca aberto por omissão."""
    env_sem_token = {k: v for k, v in os.environ.items() if k != "ORGCONC_METRICS_TOKEN"}
    with patch.dict(os.environ, env_sem_token, clear=True), \
         patch("api.main._IS_PROD", True):
        r = client.get("/metrics")
    assert r.status_code == 404


def test_metrics_em_dev_sem_token_permanece_aberto():
    """Em dev (sem ORGCONC_ENV=production) o endpoint segue aberto para
    facilitar diagnóstico local."""
    env_sem_token = {k: v for k, v in os.environ.items() if k != "ORGCONC_METRICS_TOKEN"}
    with patch.dict(os.environ, env_sem_token, clear=True), \
         patch("api.main._IS_PROD", False):
        r = client.get("/metrics")
    assert r.status_code == 200


# ── SecurityHeadersMiddleware ────────────────────────────────────────────────

def test_security_headers_presentes_em_qualquer_resposta():
    r = client.get("/health")
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert r.headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert r.headers["X-XSS-Protection"] == "0"  # header legado desativado de propósito
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_security_headers_em_resposta_de_erro_tambem():
    """Headers valem para TODA resposta, inclusive 404 — erro não pode ser
    a brecha sem CSP."""
    r = client.get("/rota-que-nao-existe-xyz")
    assert "Content-Security-Policy" in r.headers
    assert r.headers["X-Frame-Options"] == "DENY"


def test_security_headers_cache_no_store_em_rotas_sensiveis():
    """/auth/* e /export/* nunca podem ser cacheados (tokens, relatórios
    financeiros) — Cache-Control: no-store mesmo em resposta de erro."""
    r = client.post("/auth/refresh")
    assert r.headers.get("Cache-Control") == "no-store"


def test_security_headers_cache_normal_fora_das_rotas_sensiveis():
    r = client.get("/health")
    assert r.headers.get("Cache-Control") != "no-store"


# ── escopo_cliente_listagem ──────────────────────────────────────────────────

def _user(role: str, cliente_id: str | None = None):
    from api.services.auth import TokenPayload
    return TokenPayload(sub="t@orgconc.com", role=role, cliente_id=cliente_id)


@pytest.mark.parametrize("role", ["admin", "auditor", "service"])
def test_escopo_privilegiado_passa_cliente_solicitado(role):
    """Roles privilegiados não sofrem filtro: o cliente_id solicitado (ou
    None) é devolvido como veio."""
    from api.services.auth import escopo_cliente_listagem
    assert escopo_cliente_listagem(_user(role), "c-123") == "c-123"
    assert escopo_cliente_listagem(_user(role), None) is None


def test_escopo_anonymous_em_producao_recebe_403():
    """Defesa em profundidade: current_user nunca emite anonymous em prod,
    mas se emitir (regressão), a listagem nega."""
    from api.services.auth import escopo_cliente_listagem
    with patch("api.services.auth._IS_PROD", True):
        with pytest.raises(HTTPException) as exc:
            escopo_cliente_listagem(_user("anonymous"))
    assert exc.value.status_code == 403


def test_escopo_anonymous_em_dev_passa_sem_filtro():
    """Conveniência de dev/staging sem auth: anonymous lista sem filtro."""
    from api.services.auth import escopo_cliente_listagem
    with patch("api.services.auth._IS_PROD", False):
        assert escopo_cliente_listagem(_user("anonymous"), "c-9") == "c-9"
        assert escopo_cliente_listagem(_user("anonymous")) is None


def test_escopo_user_com_cliente_id_forca_o_proprio():
    from api.services.auth import escopo_cliente_listagem
    assert escopo_cliente_listagem(_user("user", "c-meu"), None) == "c-meu"
    assert escopo_cliente_listagem(_user("user", "c-meu"), "c-meu") == "c-meu"


def test_escopo_user_pedindo_outro_cliente_recebe_403():
    from api.services.auth import escopo_cliente_listagem
    with pytest.raises(HTTPException) as exc:
        escopo_cliente_listagem(_user("user", "c-meu"), "c-alheio")
    assert exc.value.status_code == 403


def test_escopo_user_multiorg_sem_cliente_id_lista_sem_filtro_de_cliente():
    """Usuário multi-org (cliente_id=None): o escopo é a org inteira — o
    isolamento fica com o RLS por org_id no banco."""
    from api.services.auth import escopo_cliente_listagem
    assert escopo_cliente_listagem(_user("user", None), None) is None
