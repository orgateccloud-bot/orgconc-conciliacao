"""Testes do scaffold SERPRO-ready (auth/transporte; Fase 1, IC-02).

Cobrem o que está implementado (gate de credenciais + fluxo OAuth2 de token com
httpx mockado). O mapeamento IC-02↔SERPRO é spec-pending e não é testado aqui.
"""
from datetime import date

import pytest

from api.core import config
from api.services import serpro_client
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


# ── Mapeamento IC-02 ↔ SERPRO (resposta ROCDomain REAL gravada da Calculadora) ──

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


def test_ic02_para_serpro_monta_payload():
    p = calc._ic02_para_serpro(_op())
    assert p["id"] == "D1"
    assert p["municipio"] == 5208707 and isinstance(p["municipio"], int)
    assert p["uf"] == "GO"
    assert p["itens"][0]["baseCalculo"] == 1000.0
    assert p["itens"][0]["ncm"] == "22021000"
    assert p["dataHoraEmissao"].startswith("2026-02-01T")


def test_serpro_para_ic02_achata_roc():
    ap = calc._serpro_para_ic02(_ROC_REAL, _op())
    assert ap.base_calculo_total == 1000.0
    assert ap.gIBSUF.pIBSUF == 0.10 and ap.gIBSUF.vIBSUF == 1.0
    assert ap.gCBS.pCBS == 0.90 and ap.gCBS.vCBS == 9.0
    assert ap.vTotTrib == 10.0
    assert ap.itens[0].vCBS == 9.0 and ap.itens[0].cClassTrib == "000001"
    assert "SERPRO" in ap.motor_versao
