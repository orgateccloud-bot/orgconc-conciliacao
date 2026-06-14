"""Robustez da integração CBS/IBS (W2 — onda P0.2).

Blinda os DOIS caminhos de erro que hoje viram 500 cru em produção:

- #5  `_num()` em `calculadora_cbs_ibs.py`: resposta da Calculadora com valor
      não-numérico ('', 'N/A', None aninhado, bool, lista, dict) NÃO pode derrubar
      a apuração — deve cair p/ 0.0 e logar o valor problemático. O caminho de
      navegação aninhada (grupos null/não-dict) também não pode estourar.
- #6  `chamar_calculadora()` em `calculadora_client.py`: HTTP 4xx/5xx, timeout,
      erro de conexão e corpo não-JSON/não-objeto devem virar a exceção de
      DOMÍNIO `CalculadoraIndisponivel` (que o router mapeia p/ 502/503), nunca
      um 500 cru de httpx/json.

O contrato de SUCESSO (IC-02) NÃO muda — só os caminhos de erro são blindados.
"""
import logging

import httpx
import pytest

from api.core import config
from api.schemas_cbs_ibs import ItemOperacao, OperacaoFiscalInput
from api.services import calculadora_cbs_ibs as calc
from api.services import calculadora_client


# ── #5: _num() resiliente ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "valor",
    ["", None, "N/A", "  ", "1.000,00", "abc", [], {}, ["1"], {"v": 1}, object()],
)
def test_num_valor_invalido_vira_zero_sem_levantar(valor):
    # Nenhum valor problemático pode levantar — sempre cai p/ 0.0.
    assert calc._num(valor) == 0.0


def test_num_valor_valido_converte():
    assert calc._num("1000.00") == 1000.0
    assert calc._num(42) == 42.0
    assert calc._num(3.14) == 3.14
    assert calc._num("0") == 0.0


def test_num_booleano_nao_silencia_como_1():
    # bool é subclasse de int: float(True)==1.0 mascararia um valor inválido.
    assert calc._num(True) == 0.0
    assert calc._num(False) == 0.0


@pytest.mark.parametrize("valor", ["inf", "-inf", "nan", "Infinity", float("inf"), float("nan")])
def test_num_nao_finito_vira_zero(valor):
    # float('inf')/('nan') passam por float() mas estouram a serialização JSON
    # do router (allow_nan=False → 500). Devem virar 0.0.
    assert calc._num(valor) == 0.0


def test_str_coage_campos_textuais():
    # cst/cClassTrib podem vir como int (0) ou None; ItemApurado exige str.
    assert calc._str(0) == "0"
    assert calc._str(None) == ""
    assert calc._str("03") == "03"


def test_num_loga_valor_problematico(caplog):
    with caplog.at_level(logging.WARNING):
        calc._num("N/A", campo="item.gCBS.vCBS")
    assert "item.gCBS.vCBS" in caplog.text
    assert "N/A" in caplog.text


def _op():
    return OperacaoFiscalInput(
        documento_id="D1",
        uf="GO",
        municipio_ibge="5208707",
        data_fato_gerador="2026-02-01",
        itens=[ItemOperacao(numero=1, ncm="22021000", cst="000",
                            cClassTrib="000001", base_calculo=1000.0)],
    )


def test_rtc_para_ic02_com_valores_nao_numericos_nao_levanta():
    """Resposta plausível da Calculadora com sujeira nos campos numéricos:
    a apuração tem de completar (valores sujos viram 0.0), sem 500."""
    roc_sujo = {
        "objetos": [
            {
                "nObj": 1,
                "tribCalc": {
                    "IBSCBS": {
                        "CST": "000",
                        "cClassTrib": "000001",
                        "gIBSCBS": {
                            "vBC": "N/A",
                            "gIBSUF": {"pIBSUF": "", "vIBSUF": None, "memoriaCalculo": "m"},
                            "gIBSMun": {"pIBSMun": "abc", "vIBSMun": "1.00"},
                            "gCBS": {"pCBS": "0.90", "vCBS": "x"},
                        },
                    }
                },
            }
        ],
        "total": {
            "tribCalc": {
                "IBSCBSTot": {
                    "vBCIBSCBS": "",
                    "gIBS": {"gIBSUF": {"vIBSUF": "N/A"}, "gIBSMun": {"vIBSMun": "1.00"}},
                    "gCBS": {"vCBS": None},
                }
            }
        },
    }
    ap = calc._rtc_para_ic02(roc_sujo, _op())
    # Campos sujos viraram 0.0; o que era numérico válido foi preservado.
    assert ap.gIBSUF.vIBSUF == 0.0
    assert ap.gIBSMun.vIBSMun == 1.0
    assert ap.gCBS.vCBS == 0.0
    assert ap.gIBSMun.pIBSMun == 0.0  # 'abc' → 0.0
    assert ap.gCBS.pCBS == 0.90
    assert ap.vTotTrib >= 0.0


def test_rtc_para_ic02_grupos_null_nao_levanta():
    """Grupos aninhados null/não-dict ({"gIBSUF": null}, objetos sujos):
    `d.get(k, {})` devolveria None e o .get() seguinte estouraria AttributeError.
    A blindagem (_obj) tem de manter a apuração de pé."""
    roc_null = {
        "objetos": [
            {"nObj": 1, "tribCalc": {"IBSCBS": {"gIBSCBS": {
                "vBC": "1000.00",
                "gIBSUF": None,
                "gIBSMun": "lixo",
                "gCBS": {"vCBS": "9.00"},
            }}}},
            "objeto-nao-dict",  # item inválido na lista → ignorado, sem crash
        ],
        "total": {"tribCalc": {"IBSCBSTot": {"gIBS": None, "gCBS": None}}},
    }
    ap = calc._rtc_para_ic02(roc_null, _op())
    assert ap.gCBS.vCBS == 9.0           # fallback p/ soma dos itens
    assert ap.gIBSUF.vIBSUF == 0.0
    assert ap.base_calculo_total == 1000.0
    # memoriaCalculo continua str (schema IC-02 §5), mesmo com grupo ausente.
    assert isinstance(ap.gIBSUF.memoriaCalculo, str)


def test_rtc_para_ic02_memoria_nao_string_coage():
    roc = {
        "objetos": [{"nObj": 1, "tribCalc": {"IBSCBS": {"gIBSCBS": {
            "vBC": "100.00",
            "gIBSUF": {"vIBSUF": "1.00", "memoriaCalculo": 123},  # número, não str
            "gCBS": {"vCBS": "1.00", "memoriaCalculo": None},
        }}}}],
        "total": {},
    }
    ap = calc._rtc_para_ic02(roc, _op())
    assert isinstance(ap.gIBSUF.memoriaCalculo, str) and ap.gIBSUF.memoriaCalculo == "123"
    assert ap.gCBS.memoriaCalculo == ""


# ── #6: chamar_calculadora() converte falha externa em erro de domínio ──────


class _ClienteQueLevanta:
    """Fake do httpx.AsyncClient cujo .post levanta uma exceção configurável."""

    exc: Exception = RuntimeError("nao configurado")

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None, **k):
        raise type(self).exc


class _RespStatusErro:
    """Resposta cujo raise_for_status levanta HTTPStatusError (HTTP 5xx/4xx)."""

    def __init__(self, status):
        self.status_code = status

    def raise_for_status(self):
        req = httpx.Request("POST", "http://x/api")
        resp = httpx.Response(self.status_code, request=req)
        raise httpx.HTTPStatusError("erro", request=req, response=resp)

    def json(self):  # não deve ser alcançado
        return {}


class _RespJSONInvalido:
    """Resposta 200 OK cujo corpo NÃO é JSON."""

    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        raise ValueError("Expecting value: line 1 column 1 (char 0)")


class _RespJSONNaoObjeto:
    """Resposta 200 OK cujo JSON é uma lista (esperávamos objeto)."""

    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return [1, 2, 3]


def _mock_post_resp(monkeypatch, resp):
    """Faz o AsyncClient.post devolver `resp` (com raise_for_status/json próprios)."""

    class _Cli:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None, **k):
            return resp

    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "http://x/api")
    monkeypatch.setattr(calculadora_client.httpx, "AsyncClient", _Cli)


@pytest.mark.asyncio
async def test_http_500_vira_indisponivel(monkeypatch):
    _mock_post_resp(monkeypatch, _RespStatusErro(500))
    with pytest.raises(calculadora_client.CalculadoraIndisponivel) as ei:
        await calculadora_client.chamar_calculadora({"a": 1})
    assert ei.value.status_http == 500


@pytest.mark.asyncio
async def test_http_400_vira_indisponivel(monkeypatch):
    _mock_post_resp(monkeypatch, _RespStatusErro(400))
    with pytest.raises(calculadora_client.CalculadoraIndisponivel) as ei:
        await calculadora_client.chamar_calculadora({"a": 1})
    assert ei.value.status_http == 400


@pytest.mark.asyncio
async def test_timeout_vira_indisponivel(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "http://x/api")
    _ClienteQueLevanta.exc = httpx.ReadTimeout("timed out")
    monkeypatch.setattr(calculadora_client.httpx, "AsyncClient", _ClienteQueLevanta)
    with pytest.raises(calculadora_client.CalculadoraIndisponivel) as ei:
        await calculadora_client.chamar_calculadora({"a": 1})
    assert ei.value.status_http is None


@pytest.mark.asyncio
async def test_erro_conexao_vira_indisponivel(monkeypatch):
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "http://x/api")
    _ClienteQueLevanta.exc = httpx.ConnectError("connection refused")
    monkeypatch.setattr(calculadora_client.httpx, "AsyncClient", _ClienteQueLevanta)
    with pytest.raises(calculadora_client.CalculadoraIndisponivel):
        await calculadora_client.chamar_calculadora({"a": 1})


@pytest.mark.asyncio
async def test_json_invalido_vira_indisponivel(monkeypatch):
    _mock_post_resp(monkeypatch, _RespJSONInvalido())
    with pytest.raises(calculadora_client.CalculadoraIndisponivel):
        await calculadora_client.chamar_calculadora({"a": 1})


@pytest.mark.asyncio
async def test_json_nao_objeto_vira_indisponivel(monkeypatch):
    _mock_post_resp(monkeypatch, _RespJSONNaoObjeto())
    with pytest.raises(calculadora_client.CalculadoraIndisponivel):
        await calculadora_client.chamar_calculadora({"a": 1})


@pytest.mark.asyncio
async def test_indisponivel_nao_vaza_traceback_httpx(monkeypatch, caplog):
    """A mensagem da exceção de domínio é limpa (sem traceback httpx/json cru)."""
    _mock_post_resp(monkeypatch, _RespStatusErro(503))
    with caplog.at_level(logging.WARNING):
        with pytest.raises(calculadora_client.CalculadoraIndisponivel) as ei:
            await calculadora_client.chamar_calculadora({"a": 1})
    msg = str(ei.value)
    assert "Calculadora" in msg and "503" in msg
    assert "Traceback" not in msg


@pytest.mark.asyncio
async def test_sucesso_continua_devolvendo_dict(monkeypatch):
    """Caminho feliz intacto: corpo JSON-objeto é devolvido como dict."""

    class _RespOk:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"total": {"tribCalc": {}}}

    _mock_post_resp(monkeypatch, _RespOk())
    out = await calculadora_client.chamar_calculadora({"a": 1}, caminho="regime-geral")
    assert out == {"total": {"tribCalc": {}}}
