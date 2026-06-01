"""Smoke test de export — exporta um relatório em HTML/XLSX/PDF a partir de um
dataset fixo, SEM chamar LLM e sem tocar dados de produção.

Exercita o caminho de render ponta a ponta (render_html / render_pdf_html +
WeasyPrint). Quando WeasyPrint não está disponível (host sem libpango), o
endpoint cai no fallback HTML — o teste aceita ambos, mas exige `%PDF` quando o
content-type é application/pdf. Serve como regressão da correção que instalou as
libs do WeasyPrint na imagem de produção.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.auth import current_user
from api.services.storage import salvar_dataset

client = TestClient(app)

_OWNER = "smoke-test"

_EXTRATOS = [
    {
        "arquivo": "smoke.ofx",
        "conta": "AG 0001-0 / CC 0001-1",
        "qtd": 3,
        "transacoes": [
            {"conta": "AG 0001-0 / CC 0001-1", "data": "2026-05-01", "tipo": "CREDIT",
             "valor": 5000.0, "memo": "PIX SMOKE", "nome": "TESTER", "checknum": ""},
            {"conta": "AG 0001-0 / CC 0001-1", "data": "2026-05-02", "tipo": "DEBIT",
             "valor": -100.0, "memo": "TARIFA", "nome": "", "checknum": ""},
            {"conta": "AG 0001-0 / CC 0001-1", "data": "2026-05-02", "tipo": "DEBIT",
             "valor": -100.0, "memo": "TARIFA", "nome": "", "checknum": ""},
        ],
    }
]
_ANOMALIAS = [
    {"severidade": "alerta", "tipo": "Duplicidade", "titulo": "Tarifa duplicada",
     "conta": "AG 0001-0 / CC 0001-1", "valor": -100.0,
     "detalhe": "Duas tarifas idênticas em 2026-05-02"},
]
_RELATORIO = (
    "# Relatório de Conciliação Bancária\n\n"
    "## Resumo Executivo\n\n"
    "Conta com 3 lançamentos e 1 anomalia (duplicidade de tarifa).\n\n"
    "## Achados\n\n- Tarifa duplicada em 2026-05-02 (R$ 100,00)\n"
)


@pytest.fixture(autouse=True)
def _auth_override():
    """Usuário determinístico via override de dependência (independe de .env/auth).

    Escopado por teste e revertido no teardown para não vazar para outros módulos.
    """
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(sub=_OWNER, role="service")
    yield
    app.dependency_overrides.pop(current_user, None)


@pytest.fixture(scope="module")
def rid() -> str:
    return salvar_dataset(_EXTRATOS, _ANOMALIAS, _RELATORIO, owner_sub=_OWNER)


def test_export_html(rid):
    r = client.get(f"/export/html/{rid}")
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers["content-type"]
    assert b"Relat" in r.content


def test_export_xlsx(rid):
    r = client.get(f"/export/xlsx/{rid}")
    assert r.status_code == 200, r.text
    assert r.content[:2] == b"PK"  # XLSX é um arquivo ZIP
    assert len(r.content) > 2000


def test_export_pdf_renderiza_pdf(rid):
    try:
        import weasyprint  # noqa: F401

        weasyprint_ok = True
    except Exception:
        weasyprint_ok = False

    r = client.get(f"/export/pdf/{rid}")
    assert r.status_code == 200, r.text
    ct = r.headers.get("content-type", "")
    if weasyprint_ok:
        # Onde o WeasyPrint existe (CI com libpango, prod) o PDF DEVE sair — sem
        # fallback. Se as libs de sistema estiverem incompletas, o render falha e
        # cai no HTML; este assert estrito flagra isso (a classe de bug do PDF mudo).
        assert ct.startswith("application/pdf"), f"WeasyPrint disponível mas caiu no fallback: {ct}"
        assert r.content[:4] == b"%PDF", f"primeiros bytes: {r.content[:8]!r}"
        assert len(r.content) > 1000
    else:
        # Host sem libpango (ex.: Windows dev) → fallback HTML imprimível é aceitável
        assert "text/html" in ct
        assert b"Relat" in r.content


def test_export_pdf_query_html_retorna_html(rid):
    r = client.get(f"/export/pdf/{rid}?html=true")
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers["content-type"]


def test_export_id_invalido_400(rid):
    assert client.get("/export/html/XYZ").status_code == 400


def test_export_id_inexistente_404():
    # 12 chars hex válidos no formato, mas dataset não existe
    assert client.get("/export/html/aaaaaaaaaaaa").status_code == 404
