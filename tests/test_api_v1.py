"""Versionamento /v1 (dual-mount, P2 #10).

As rotas de negócio respondem em /v1/* E na raiz (retrocompat do frontend).
auth/sessão, /metrics e /app ficam fora do /v1 de propósito (cookie de refresh
com path fixo /auth; infra não-versionada). OpenAPI documenta só a raiz.
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_v1_health_espelha_health_raiz():
    raiz = client.get("/health")
    v1 = client.get("/v1/health")
    assert v1.status_code == raiz.status_code == 200
    assert v1.json().keys() == raiz.json().keys()
    assert v1.json()["status"] == raiz.json()["status"]


def test_v1_rotas_de_negocio_existem():
    # Mesmo status nas duas montagens (sem asserir corpo: depende de DB).
    for caminho in ("/conciliacoes", "/clientes"):
        raiz = client.get(caminho)
        v1 = client.get("/v1" + caminho)
        assert v1.status_code == raiz.status_code, caminho
        assert v1.status_code != 404, f"/v1{caminho} deveria existir"


def test_auth_fica_fora_do_v1():
    # Sessão por cookie (path=/auth) não é versionada — /v1/auth não existe.
    assert client.post("/v1/auth/login", json={"email": "x@y.com", "senha": "12345678"}).status_code == 404
    assert client.post("/auth/login", json={"email": "x@y.com", "senha": "12345678"}).status_code != 404


def test_openapi_documenta_so_o_caminho_canonico():
    paths = app.openapi()["paths"]
    assert "/health" in paths
    assert not any(p.startswith("/v1/") for p in paths), \
        "rotas /v1 não devem duplicar o schema OpenAPI"
