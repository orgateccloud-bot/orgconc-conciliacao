"""Testes do cliente de transporte da Calculadora oficial (RTC, IC-02).

SERPRO foi excluído como alvo (2026-06-09): não há mais OAuth2/Consumer-Key.
O transporte é aberto (instância oficial consumo.tributos.gov.br / offline local,
sem autenticação). Cobrem transporte (POST), pre-flight de versão e o mapeamento
IC-02↔RTC. O mapeamento completo valida contra a instância oficial.
"""
import logging
from datetime import date

import pytest

from api.core import config
from api.services import calculadora_client
from api.services import calculadora_cbs_ibs as calc
from api.schemas_cbs_ibs import ItemOperacao, OperacaoFiscalInput


class _FakeResp:
    def __init__(self, data, status=200):
        self._d = data
        self.status_code = status

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


class _FakePostClient:
    """Fake do httpx.AsyncClient que captura o POST e devolve um JSON fixo."""

    captured: dict = {}
    resposta: dict = {"ok": True}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None, **k):
        _FakePostClient.captured = {"url": url, "headers": headers or {}, "json": json}
        return _FakeResp(_FakePostClient.resposta)


# ── Transporte (POST) — instância aberta, sem auth ──


@pytest.mark.asyncio
async def test_chamar_calculadora_sem_url_levanta_config_error(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "")
    with pytest.raises(calculadora_client.CalculadoraConfigError):
        await calculadora_client.chamar_calculadora({"x": 1})


@pytest.mark.asyncio
async def test_chamar_calculadora_post_sem_auth(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "http://x/api")
    monkeypatch.setattr(calculadora_client.httpx, "AsyncClient", _FakePostClient)
    _FakePostClient.resposta = {"total": 1}
    out = await calculadora_client.chamar_calculadora({"a": 1}, caminho="regime-geral")
    assert out == {"total": 1}
    cap = _FakePostClient.captured
    assert cap["url"] == "http://x/api/regime-geral"
    assert cap["json"] == {"a": 1}
    # Instância aberta: NUNCA envia Authorization.
    assert "Authorization" not in cap["headers"]


# ── Pre-flight de versão da base (GET /versao/status) ──


class _FakeVersaoClient:
    """Fake do httpx.AsyncClient que responde ao GET /versao/status."""

    versao = "V0033"
    captured: dict = {}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None, **k):
        _FakeVersaoClient.captured = {"headers": headers or {}}
        return _FakeResp({"versaoDbLocal": _FakeVersaoClient.versao})


@pytest.mark.asyncio
async def test_obter_versao_db_parseia(monkeypatch):
    # Fake responde só o formato LEGADO (versaoDbLocal) — exercita o fallback.
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "http://x/api")
    _FakeVersaoClient.versao = "V0029"
    monkeypatch.setattr(calculadora_client.httpx, "AsyncClient", _FakeVersaoClient)
    calculadora_client._reset_versao_cache()
    assert await calculadora_client.obter_versao_db() == "V0029"
    # Instância aberta: sem Authorization no pre-flight.
    assert "Authorization" not in _FakeVersaoClient.captured["headers"]


class _FakeVersaoOficialClient:
    """Responde o caminho OFICIAL (dados-abertos/versao → versaoDb) e registra
    as URLs consultadas — formato verificado live na produção (2026-06-10)."""

    urls: list = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None, **k):
        _FakeVersaoOficialClient.urls.append(url)
        if url.endswith("/calculadora/dados-abertos/versao"):
            return _FakeResp({"versaoApp": "1.2.1", "versaoDb": "V0033", "ambiente": "pro"})
        return _FakeResp({}, status=404)


@pytest.mark.asyncio
async def test_obter_versao_db_prefere_caminho_oficial(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "http://x/api")
    monkeypatch.setattr(calculadora_client.httpx, "AsyncClient", _FakeVersaoOficialClient)
    _FakeVersaoOficialClient.urls = []
    calculadora_client._reset_versao_cache()
    assert await calculadora_client.obter_versao_db() == "V0033"
    # Achou no caminho oficial — não cai no legado /versao/status.
    assert _FakeVersaoOficialClient.urls == ["http://x/api/calculadora/dados-abertos/versao"]


@pytest.mark.asyncio
async def test_obter_versao_db_sem_url_devolve_none(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "")
    calculadora_client._reset_versao_cache()
    assert await calculadora_client.obter_versao_db() is None


@pytest.mark.asyncio
async def test_checar_versao_base_avisa_em_mismatch(monkeypatch, caplog):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "http://x/api")
    monkeypatch.setattr(config, "CBS_IBS_VERSAO_BASE", "V0033")
    _FakeVersaoClient.versao = "V0029"
    monkeypatch.setattr(calculadora_client.httpx, "AsyncClient", _FakeVersaoClient)
    calculadora_client._reset_versao_cache()
    with caplog.at_level(logging.WARNING):
        v = await calculadora_client.checar_versao_base()
    assert v == "V0029"
    assert "divergente" in caplog.text


@pytest.mark.asyncio
async def test_checar_versao_base_silencioso_em_match(monkeypatch, caplog):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "http://x/api")
    monkeypatch.setattr(config, "CBS_IBS_VERSAO_BASE", "V0033")
    _FakeVersaoClient.versao = "V0033"
    monkeypatch.setattr(calculadora_client.httpx, "AsyncClient", _FakeVersaoClient)
    calculadora_client._reset_versao_cache()
    with caplog.at_level(logging.WARNING):
        v = await calculadora_client.checar_versao_base()
    assert v == "V0033"
    assert "divergente" not in caplog.text


# ── Mapeamento IC-02 ↔ RTC (resposta ROCDomain REAL gravada da Calculadora) ──

_ROC_REAL = {
    "objetos": [
        {
            "nObj": 1,
            "tribCalc": {
                "IBSCBS": {
                    "CST": "000",
                    "cClassTrib": "000001",
                    "gIBSCBS": {
                        "vBC": "1000.00",
                        "gIBSUF": {"pIBSUF": "0.10", "vIBSUF": "1.00", "memoriaCalculo": "mem-uf"},
                        "gIBSMun": {"pIBSMun": "0.00", "vIBSMun": "0.00", "memoriaCalculo": "mem-mun"},
                        "vIBS": "1.00",
                        "gCBS": {"pCBS": "0.90", "vCBS": "9.00", "memoriaCalculo": "mem-cbs"},
                    },
                }
            },
        }
    ],
    "total": {
        "tribCalc": {
            "IBSCBSTot": {
                "vBCIBSCBS": "1000.00",
                "gIBS": {"gIBSUF": {"vIBSUF": "1.00"}, "gIBSMun": {"vIBSMun": "0.00"}, "vIBS": "1.00"},
                "gCBS": {"vCBS": "9.00"},
            }
        }
    },
}


def _op():
    return OperacaoFiscalInput(
        documento_id="D1",
        uf="GO",
        municipio_ibge="5208707",
        data_fato_gerador=date(2026, 2, 1),
        itens=[ItemOperacao(numero=1, ncm="22021000", cst="000", cClassTrib="000001", base_calculo=1000.0)],
    )


def test_ic02_para_rtc_monta_payload():
    p = calc._ic02_para_rtc(_op())
    assert p["id"] == "D1"
    assert p["municipio"] == 5208707 and isinstance(p["municipio"], int)
    assert p["uf"] == "GO"
    assert p["itens"][0]["baseCalculo"] == 1000.0
    assert p["itens"][0]["ncm"] == "22021000"
    # dhFatoGerador substitui o deprecated dataHoraEmissao (validado live 2026-06-10).
    assert p["dhFatoGerador"].startswith("2026-02-01T")
    assert "dataHoraEmissao" not in p


def test_rtc_para_ic02_achata_roc():
    ap = calc._rtc_para_ic02(_ROC_REAL, _op())
    assert ap.base_calculo_total == 1000.0
    assert ap.gIBSUF.pIBSUF == 0.10 and ap.gIBSUF.vIBSUF == 1.0
    assert ap.gCBS.pCBS == 0.90 and ap.gCBS.vCBS == 9.0
    assert ap.vTotTrib == 10.0
    assert ap.itens[0].vCBS == 9.0 and ap.itens[0].cClassTrib == "000001"
    assert "RTC" in ap.motor_versao
