"""Fallback SPA do mount /app (bug de produção 2026-06-11).

Deep-link/F5 em rota interna (GET /app/laudo) devolvia 404 do FastAPI: o
StaticFiles(html=True) só serve index.html na raiz do mount. SPAStaticFiles
serve o index.html para 404 SEM extensão (rota de página do React Router);
caminho COM extensão segue 404 real (asset quebrado não vira HTML mascarado).

Os testes principais usam um dist sintético (tmp_path) — rodam no CI sem build
do frontend. O teste contra o app real só roda quando orgconc-react/dist existe.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.core.config import REACT_DIST
from api.core.spa_static import SPAStaticFiles

INDEX_HTML = "<!doctype html><html><body><div id='root'>OrgConc SPA</div></body></html>"


@pytest.fixture()
def cliente_spa(tmp_path):
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
    app = FastAPI()
    app.mount("/app", SPAStaticFiles(directory=str(tmp_path), html=True), name="spa")
    return TestClient(app)


def test_rota_de_pagina_sem_extensao_serve_index(cliente_spa):
    for rota in ("/app/laudo", "/app/clientes", "/app/auditoria-forense/detalhe"):
        r = cliente_spa.get(rota)
        assert r.status_code == 200, rota
        assert "OrgConc SPA" in r.text, rota
        assert r.headers["content-type"].startswith("text/html"), rota


def test_asset_real_continua_servido(cliente_spa):
    r = cliente_spa.get("/app/assets/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_asset_inexistente_com_extensao_da_404_real(cliente_spa):
    # Decisão documentada: caminho com extensão NÃO cai no fallback — um bundle
    # quebrado deve falhar visível, não receber HTML no lugar de JS.
    assert cliente_spa.get("/app/assets/nao-existe.js").status_code == 404
    assert cliente_spa.get("/app/qualquer.png").status_code == 404


def test_raiz_do_mount_segue_servindo_index(cliente_spa):
    r = cliente_spa.get("/app/")
    assert r.status_code == 200
    assert "OrgConc SPA" in r.text


@pytest.mark.skipif(not REACT_DIST.exists(), reason="build do React ausente (CI não builda no job pytest)")
def test_app_real_deep_link_serve_index():
    from api.main import app

    r = TestClient(app).get("/app/laudo")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
