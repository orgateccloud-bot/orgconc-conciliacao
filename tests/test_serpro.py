"""Testes da integracao SERPRO.

CPF valido usado: 111.444.777-35 (DV correto).
CNPJ valido usado: 11.222.333/0001-81 (DV correto).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["ORGCONC_DATA_DIR"] = str(Path(__file__).resolve().parent / "_data_test_serpro")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.main import app
import api.services.serpro_consulta as serpro_module

CPF_VALIDO = "111.444.777-35"
CNPJ_VALIDO = "11.222.333/0001-81"

# Stub completo do serpro_client.py com logica real de mapeamento HTTP->excecoes.
_STUB = """
import re as _re

class SerproError(Exception): pass
class SerproDocumentoInvalido(SerproError): pass
class SerproNaoEncontrado(SerproError): pass
class SerproMenorDeIdade(SerproError): pass
class SerproRateLimitError(SerproError): pass
class SerproNetworkError(SerproError): pass
class SerproAuthError(SerproError): pass
class SerproConfigError(SerproError): pass

class ResultadoConsulta:
    def __init__(self, tipo, documento_mascarado, parcial, dados):
        self.tipo = tipo
        self.documento_mascarado = documento_mascarado
        self.parcial = parcial
        self.dados = dados

def _valida_cpf(cpf):
    d = _re.sub(r'\\D', '', cpf)
    if len(d) != 11:
        raise SerproDocumentoInvalido(f'CPF invalido: {cpf}')
    def _c(digits, pesos):
        s = sum(int(digits[i]) * pesos[i] for i in range(len(pesos)))
        r = s % 11
        return 0 if r < 2 else 11 - r
    if int(d[9]) != _c(d, [10,9,8,7,6,5,4,3,2]) or int(d[10]) != _c(d, [11,10,9,8,7,6,5,4,3,2]):
        raise SerproDocumentoInvalido(f'CPF invalido: {cpf}')
    return d

def _valida_cnpj(cnpj):
    d = _re.sub(r'\\D', '', cnpj)
    if len(d) != 14:
        raise SerproDocumentoInvalido(f'CNPJ invalido: {cnpj}')
    return d

def _check_status(resp, doc_tipo):
    sc = resp.status_code
    if sc in (200, 206):
        return
    if sc == 404:
        raise SerproNaoEncontrado(f'{doc_tipo} nao encontrado')
    if sc == 429:
        raise SerproRateLimitError('cota excedida')
    if sc == 422:
        try: body = resp.json()
        except Exception: body = {}
        if body.get('motivo') == 'DV001':
            raise SerproMenorDeIdade('menor de idade')
        detail = body.get('mensagem','') or body.get('code','') or str(sc)
        raise SerproError(f'gateway 422: {detail}')
    if sc in (401, 403):
        raise SerproError(f'gateway {sc}')
    raise SerproError(f'gateway {sc}')

class SerproClient:
    def __init__(self, **kw):
        self._audit_hook = kw.get('audit_hook')
        self._audit_salt = kw.get('audit_salt')

    def _get_autenticado(self, url):
        raise NotImplementedError('deve ser mockado nos testes')

    def _emit_audit(self, tipo, mask):
        if self._audit_hook:
            self._audit_hook({
                'evento': 'consulta_serpro',
                'tipo': tipo,
                'documento_mascarado': mask,
                'documento_hash': 'hash_fake_' + (self._audit_salt or ''),
                'resultado': 'ok',
            })

    def consultar_cpf(self, cpf):
        digits = _valida_cpf(cpf)
        resp = self._get_autenticado(f'/cpf/{digits}')
        _check_status(resp, 'CPF')
        data = resp.json()
        parcial = resp.status_code == 206
        dados = {
            'nome': data.get('nome'),
            'situacao_codigo': data.get('situacao', {}).get('codigo'),
            'situacao_descricao': data.get('situacao', {}).get('descricao'),
            'data_nascimento': data.get('dataNascimento'),
        }
        mask = '***.***.***-**'
        resultado = ResultadoConsulta('Pessoa Fisica', mask, parcial, dados)
        self._emit_audit('cpf', mask)
        return resultado

    def consultar_cnpj(self, cnpj):
        digits = _valida_cnpj(cnpj)
        resp = self._get_autenticado(f'/cnpj/{digits}')
        _check_status(resp, 'CNPJ')
        data = resp.json()
        end = data.get('endereco', {})
        mun = end.get('municipio', {})
        dados = {
            'razao_social': data.get('nomeEmpresarial'),
            'nome_fantasia': data.get('nomeFantasia'),
            'situacao': data.get('situacaoCadastral', {}).get('descricao'),
            'data_abertura': data.get('dataAbertura'),
            'cnae_principal': data.get('cnaePrincipal', {}).get('descricao'),
            'endereco': {
                'logradouro': end.get('logradouro'),
                'numero': end.get('numero'),
                'bairro': end.get('bairro'),
                'uf': end.get('uf'),
                'municipio': mun.get('descricao') if isinstance(mun, dict) else mun,
            },
        }
        mask = '**.***.***/****-**'
        resultado = ResultadoConsulta('Pessoa Juridica', mask, False, dados)
        self._emit_audit('cnpj', mask)
        return resultado

    def fechar(self):
        pass
"""


@pytest.fixture(autouse=True)
def _config_serpro_env(tmp_path, monkeypatch):
    d = tmp_path / "serpro"
    d.mkdir()
    (d / "serpro_client.py").write_text(_STUB, encoding="utf-8")
    monkeypatch.setenv("ORGCONC_SERPRO_CLIENT_PATH", str(d))
    monkeypatch.setenv("ORGCONC_SERPRO_DEMO_TOKEN", "demo-token-fake")
    monkeypatch.setenv("ORGCONC_SERPRO_AUDIT_SALT", "pepper-de-teste")
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_SECRET", raising=False)
    serpro_module._resetar_singleton_para_testes()
    try:
        app.state.limiter.reset()
    except Exception:
        pass
    yield
    serpro_module._resetar_singleton_para_testes()


class _FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload
        self.text = "{}" if payload is None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@pytest.fixture
def api_client():
    return TestClient(app)


@pytest.fixture
def mock_serpro(api_client, monkeypatch):
    client = serpro_module.obter_client()
    state = {"resp": None}

    def _set(resp):
        state["resp"] = resp

    def _fake(url):
        return state["resp"]

    monkeypatch.setattr(client, "_get_autenticado", _fake, raising=True)
    return _set


def test_cpf_sucesso(api_client, mock_serpro):
    mock_serpro(_FakeResponse(200, {
        "nome": "JOAO DA SILVA",
        "situacao": {"codigo": "0", "descricao": "Regular"},
        "dataNascimento": "1980-01-15",
        "dataInscricao": "2000-01-01",
    }))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 200
    body = r.json()
    assert body["tipo"].startswith("Pessoa F")
    assert body["parcial"] is False
    assert body["dados"]["nome"] == "JOAO DA SILVA"
    assert body["dados"]["situacao_descricao"] == "Regular"


def test_cnpj_sucesso(api_client, mock_serpro):
    mock_serpro(_FakeResponse(200, {
        "nomeEmpresarial": "ORGATEC CONTABIL LTDA",
        "nomeFantasia": "OrgConc",
        "situacaoCadastral": {"descricao": "ATIVA"},
        "dataAbertura": "2020-01-01",
        "cnaePrincipal": {"descricao": "Atividades de contabilidade"},
        "endereco": {
            "logradouro": "Av Paulista", "numero": "1000", "bairro": "Bela Vista",
            "uf": "SP", "municipio": {"descricao": "Sao Paulo"},
        },
    }))
    r = api_client.post("/serpro/cnpj", json={"cnpj": CNPJ_VALIDO})
    assert r.status_code == 200
    body = r.json()
    assert body["dados"]["razao_social"] == "ORGATEC CONTABIL LTDA"
    assert body["dados"]["endereco"]["municipio"] == "Sao Paulo"


def test_cpf_parcial_206(api_client, mock_serpro):
    mock_serpro(_FakeResponse(206, {"nome": "X", "situacao": {"codigo": "0", "descricao": "Regular"}}))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 200
    assert r.json()["parcial"] is True


def test_cpf_nao_encontrado_404(api_client, mock_serpro):
    mock_serpro(_FakeResponse(404, {}))
    assert api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO}).status_code == 404


def test_cpf_cota_excedida_429(api_client, mock_serpro):
    mock_serpro(_FakeResponse(429, {}))
    assert api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO}).status_code == 429


def test_cpf_menor_de_idade_451(api_client, mock_serpro):
    mock_serpro(_FakeResponse(422, {"motivo": "DV001", "mensagem": "Bloqueado"}))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 451
    assert "menor de idade" in r.json()["detail"].lower()


def test_cpf_422_generico_vira_502_com_diagnostico(api_client, mock_serpro):
    mock_serpro(_FakeResponse(422, {"mensagem": "campo invalido", "code": "E_VAL"}))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert "E_VAL" in detail or "campo invalido" in detail
    assert CPF_VALIDO.replace(".", "").replace("-", "") not in detail


def test_cpf_403_sem_motivo_vira_502(api_client, mock_serpro):
    mock_serpro(_FakeResponse(403, {}))
    assert api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO}).status_code == 502


def test_cpf_formato_curto_422_pydantic(api_client):
    assert api_client.post("/serpro/cpf", json={"cpf": "abc"}).status_code == 422


def test_cnpj_dv_invalido_422_pydantic(api_client):
    assert api_client.post("/serpro/cnpj", json={"cnpj": "11.111.111/1111-11"}).status_code == 422


def test_cpf_dv_invalido_400_local(api_client, mock_serpro):
    mock_serpro(_FakeResponse(200, {}))
    r = api_client.post("/serpro/cpf", json={"cpf": "12345678900"})
    assert r.status_code == 400
    assert "invalido" in r.json()["detail"].lower()


def test_endpoints_503_sem_credenciais(tmp_path, monkeypatch):
    d = tmp_path / "s503"
    d.mkdir()
    (d / "serpro_client.py").write_text(_STUB, encoding="utf-8")
    monkeypatch.setenv("ORGCONC_SERPRO_CLIENT_PATH", str(d))
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_SECRET", raising=False)
    monkeypatch.delenv("ORGCONC_SERPRO_DEMO_TOKEN", raising=False)
    serpro_module._resetar_singleton_para_testes()
    c = TestClient(app)
    assert c.post("/serpro/cpf", json={"cpf": CPF_VALIDO}).status_code == 503
    assert c.post("/serpro/cnpj", json={"cnpj": CNPJ_VALIDO}).status_code == 503


def test_audit_hook_emite_log_estruturado(api_client, mock_serpro, caplog):
    import logging
    caplog.set_level(logging.INFO, logger="orgconc.serpro")
    mock_serpro(_FakeResponse(200, {"nome": "X", "situacao": {"codigo": "0", "descricao": "Regular"}}))
    r1 = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    r2 = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r1.status_code == 200 and r2.status_code == 200
    recs = [r for r in caplog.records if r.name == "orgconc.serpro" and getattr(r, "audit_event", None) == "consulta_serpro"]
    assert len(recs) >= 2
    hashes = [getattr(r, "documento_hash", None) for r in recs]
    assert hashes[0] is not None and hashes[0] == hashes[1]
    assert {getattr(r, "documento_mascarado", None) for r in recs} == {"***.***.***-**"}
