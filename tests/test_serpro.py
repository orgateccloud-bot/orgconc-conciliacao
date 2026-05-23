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

_STUB = (
    "class SerproError(Exception): pass\n"
    "class SerproDocumentoInvalido(SerproError): pass\n"
    "class SerproNaoEncontrado(SerproError): pass\n"
    "class SerproMenorDeIdade(SerproError): pass\n"
    "class SerproRateLimitError(SerproError): pass\n"
    "class SerproNetworkError(SerproError): pass\n"
    "class SerproAuthError(SerproError): pass\n"
    "class SerproConfigError(SerproError): pass\n"
    "class ResultadoConsulta:\n"
    "    def __init__(self,tipo,doc_mask,parcial,dados):\n"
    "        self.tipo=tipo;self.documento_mascarado=doc_mask;self.parcial=parcial;self.dados=dados\n"
    "class SerproClient:\n"
    "    def __init__(self,**kw):\n"
    "        self._audit_hook=kw.get('audit_hook');self._audit_salt=kw.get('audit_salt')\n"
    "    def _get_autenticado(self,url): raise NotImplementedError\n"
    "    def consultar_cpf(self,cpf): raise NotImplementedError\n"
    "    def consultar_cnpj(self,cnpj): raise NotImplementedError\n"
    "    def fechar(self): pass\n"
)


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
    assert body["documento_mascarado"] == "***.***.**-**"
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
    assert body["documento_mascarado"] == "**.***.***/****-**"
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
