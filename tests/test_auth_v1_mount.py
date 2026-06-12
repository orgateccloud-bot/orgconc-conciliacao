"""Dual-mount do auth sob /v1: rotas respondem na raiz E em /v1/auth/*.

O cookie httpOnly de refresh é emitido com path fixo "/auth" (escopo mínimo),
então refresh/logout via BROWSER devem usar a raiz — mas as rotas existem nos
dois mounts (clientes de API sem cookie usam /v1). Ver comentário em api/main.py.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_rotas_de_auth_existem_na_raiz_e_no_v1():
    paths = {getattr(r, "path", "") for r in app.routes}
    for rota in ("/auth/login", "/auth/refresh", "/auth/logout", "/auth/me"):
        assert rota in paths, rota
        assert f"/v1{rota}" in paths, f"/v1{rota}"


def test_login_no_v1_se_comporta_como_na_raiz():
    corpo = {"email": "sonda@inexistente.local", "senha": "invalida-123"}
    r_raiz = client.post("/auth/login", json=corpo)
    r_v1 = client.post("/v1/auth/login", json=corpo)
    # Mesmo comportamento nos dois mounts (401 com auth configurada; 503 sem).
    assert r_v1.status_code == r_raiz.status_code
    assert r_v1.status_code in (401, 503)
