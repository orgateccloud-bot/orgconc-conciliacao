"""test_cbs_ibs_fase1.py — integração CBS/IBS com o motor SERPRO (Fase 1).

Sem rede: usa httpx.MockTransport (nativo) para simular o motor no formato
SUPOSTO do contrato (ver serpro_traducao.py). Prova a tradução IC-02↔SERPRO, o
roteamento, o cliente httpx (sucesso/erro) e o dispatch da calculadora.

Quando o OpenAPI real do SERPRO chegar, ajustar serpro_traducao.py + os mocks
daqui; o cliente e o dispatch permanecem.
"""
import json
from datetime import date

import httpx
import pytest

from api.core import config
from api.schemas_cbs_ibs import ItemOperacao, OperacaoFiscalInput
from api.services import serpro_traducao as T
from api.services.serpro_client import CalculadoraIndisponivel, apurar_via_serpro


def _inp_mercadoria(base: float = 1000.0) -> OperacaoFiscalInput:
    return OperacaoFiscalInput(
        documento_id="doc-1", uf="SP", municipio_ibge="3550308",
        data_fato_gerador=date(2026, 1, 15),
        itens=[ItemOperacao(numero=1, ncm="12345678", cst="000",
                            cClassTrib="000001", base_calculo=base)],
    )


def _inp_servico() -> OperacaoFiscalInput:
    return OperacaoFiscalInput(
        documento_id="doc-2", uf="SP", municipio_ibge="3550308",
        data_fato_gerador=date(2026, 1, 15),
        itens=[ItemOperacao(numero=1, nbs="123456", cst="000",
                            cClassTrib="000001", base_calculo=500.0)],
    )


def _ibscbs(vuf: float, vcbs: float, base: float, numero: int = 1) -> dict:
    return {
        "numero": numero, "baseCalculo": base,
        "tribCalc": {"IBSCBS": {
            "gIBSUF": {"pIBSUF": 0.1, "vIBSUF": vuf, "memoriaCalculo": "uf"},
            "gIBSMun": {"pIBSMun": 0.0, "vIBSMun": 0.0, "memoriaCalculo": "mun"},
            "gCBS": {"pCBS": 0.1, "vCBS": vcbs, "memoriaCalculo": "cbs"},
        }},
    }


_RESP = {"versaoMotor": "SERPRO-1.0", "objetos": [_ibscbs(1.0, 1.0, 1000.0)]}


# ── Tradução pura (sem rede) ──────────────────────────────────────────────

def test_endpoint_roteia_mercadoria_vs_servico():
    assert T.endpoint_para(_inp_mercadoria()) == T.ROTA_REGIME_GERAL
    assert T.endpoint_para(_inp_servico()) == T.ROTA_NFSE


def test_ic02_para_serpro_mapeia_campos():
    p = T.ic02_para_serpro(_inp_mercadoria())
    assert p["id"] == "doc-1"
    assert p["codigoMunicipio"] == 3550308 and isinstance(p["codigoMunicipio"], int)
    assert p["dataHoraEmissao"] == "2026-01-15"
    assert p["objetos"][0]["baseCalculo"] == 1000.0
    assert p["objetos"][0]["ncm"] == "12345678"


def test_serpro_para_ic02_achata():
    apur = T.serpro_para_ic02(_RESP, _inp_mercadoria(), "hash123")
    assert apur.base_calculo_total == 1000.0
    assert apur.gIBSUF.vIBSUF == 1.0
    assert apur.gCBS.vCBS == 1.0
    assert apur.vTotTrib == 2.0
    assert apur.payload_hash == "hash123"
    assert apur.itens and apur.itens[0].vIBSUF == 1.0


def test_serpro_para_ic02_agrega_multiplos_objetos():
    inp = OperacaoFiscalInput(
        documento_id="doc-3", uf="SP", municipio_ibge="3550308",
        data_fato_gerador=date(2026, 1, 15),
        itens=[
            ItemOperacao(numero=1, ncm="111", cst="000", cClassTrib="000001", base_calculo=1000.0),
            ItemOperacao(numero=2, ncm="222", cst="000", cClassTrib="000001", base_calculo=2000.0),
        ],
    )
    resp = {"objetos": [_ibscbs(1.0, 1.0, 1000.0, 1), _ibscbs(2.0, 2.0, 2000.0, 2)]}
    apur = T.serpro_para_ic02(resp, inp, "h")
    assert apur.base_calculo_total == 3000.0
    assert apur.gIBSUF.vIBSUF == 3.0
    assert apur.gCBS.vCBS == 3.0
    assert apur.vTotTrib == 6.0
    assert len(apur.itens) == 2


def test_serpro_para_ic02_formato_ruim():
    with pytest.raises(T.TraducaoSerproError):
        T.serpro_para_ic02({"objetos": [{"numero": 1}]}, _inp_mercadoria(), "h")


# ── Cliente httpx (MockTransport) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_apurar_via_serpro_ok(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "https://serpro.test")
    capturado = {}

    def handler(request):
        capturado["url"] = str(request.url)
        capturado["body"] = json.loads(request.content)
        return httpx.Response(200, json=_RESP)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="https://serpro.test")
    apur = await apurar_via_serpro(_inp_mercadoria(), client=client)
    await client.aclose()

    assert apur.vTotTrib == 2.0
    assert apur.motor_versao == "SERPRO-1.0"
    assert "/regime-geral" in capturado["url"]
    assert capturado["body"]["id"] == "doc-1"


@pytest.mark.asyncio
async def test_apurar_via_serpro_status_erro_eh_tratavel(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "https://serpro.test")
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(500)),
        base_url="https://serpro.test",
    )
    with pytest.raises(CalculadoraIndisponivel):
        await apurar_via_serpro(_inp_mercadoria(), client=client)
    await client.aclose()


@pytest.mark.asyncio
async def test_apurar_via_serpro_sem_base_url(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "")
    with pytest.raises(CalculadoraIndisponivel):
        await apurar_via_serpro(_inp_mercadoria())


# ── Dispatch da calculadora ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_hospedada_usa_serpro(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_MODO", "hospedada")
    sentinela = T.serpro_para_ic02(_RESP, _inp_mercadoria(), "h")

    async def fake(inp, client=None):
        return sentinela

    monkeypatch.setattr("api.services.serpro_client.apurar_via_serpro", fake)
    from api.services.calculadora_cbs_ibs import apurar
    out = await apurar(_inp_mercadoria())
    assert out is sentinela


@pytest.mark.asyncio
async def test_dispatch_stub_nao_chama_rede(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_MODO", "stub")
    from api.services.calculadora_cbs_ibs import apurar
    apur = await apurar(_inp_mercadoria())
    assert apur.motor_versao and "stub" in apur.motor_versao.lower()
