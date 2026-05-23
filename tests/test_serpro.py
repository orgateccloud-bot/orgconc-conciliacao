"""Testes da integracao SERPRO (endpoints /serpro/cpf e /serpro/cnpj).

Estrategia: nao chamamos o gateway real. Monkeypatch do `_get_autenticado` do
SerproClient para simular respostas HTTP. Isso permite cobrir todos os caminhos
de erro sem credenciais nem cota.

CPF valido usado: 111.444.777-35 (DV correto, frequentemente usado em exemplos).
CNPJ valido usado: 11.222.333/0001-81 (DV correto).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Forca data dir temporario antes de importar app
os.environ["ORGCONC_DATA_DIR"] = str(Path(__file__).resolve().parent / "_data_test_serpro")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# NOTA: nao setamos ORGCONC_SERPRO_* no nivel do modulo porque a importacao
# de api.main dispara load_dotenv(override=True), que sobrescreveria nossos
# valores com o .env real (potencialmente vazio). Em vez disso, usamos uma
# fixture autouse com monkeypatch.setenv que roda por-teste, DEPOIS dos
# imports de modulo. monkeypatch nao eh afetado por load_dotenv subsequente.
from api.main import app
import api.services.serpro_consulta as serpro_module


CPF_VALIDO = "111.444.777-35"
CNPJ_VALIDO = "11.222.333/0001-81"


@pytest.fixture(autouse=True)
def _config_serpro_env(monkeypatch):
    """Configura env vars de SERPRO por-teste, reseta singleton e rate limiter."""
    monkeypatch.setenv("ORGCONC_SERPRO_CLIENT_PATH", r"D:\integracoes\serpro")
    monkeypatch.setenv("ORGCONC_SERPRO_DEMO_TOKEN", "demo-token-fake-para-pytest")
    monkeypatch.setenv("ORGCONC_SERPRO_AUDIT_SALT", "pepper-de-teste-determinist")
    # Garante que producao nao esteja ativa por engano.
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_SECRET", raising=False)
    serpro_module._resetar_singleton_para_testes()
    # Reseta storage do slowapi para nao acumular contagem entre testes.
    try:
        app.state.limiter.reset()
    except Exception:
        pass
    yield
    serpro_module._resetar_singleton_para_testes()


class _FakeResponse:
    """Simula requests.Response com status + payload JSON."""

    def __init__(self, status: int, payload: dict | None = None):
        self.status_code = status
        self._payload = payload
        self.text = "{}" if payload is None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@pytest.fixture
def api_client():
    """TestClient (singleton ja reiniciado pela fixture autouse)."""
    return TestClient(app)


@pytest.fixture
def mock_serpro(api_client, monkeypatch):
    """Constroi o client e instala um setter de mock para _get_autenticado."""
    client = serpro_module.obter_client()
    state = {"resp": None}

    def _set_response(resp: _FakeResponse) -> None:
        state["resp"] = resp

    def _fake_get(url: str) -> _FakeResponse:
        return state["resp"]

    monkeypatch.setattr(client, "_get_autenticado", _fake_get, raising=True)
    return _set_response


# ── Caminho feliz ──────────────────────────────────────────────────────────

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
    assert body["tipo"].startswith("Pessoa F")  # Fisica/Física
    assert body["documento_mascarado"] == "***.***.***-**"
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
    mock_serpro(_FakeResponse(206, {
        "nome": "JOAO DA SILVA",
        "situacao": {"codigo": "0", "descricao": "Regular"},
        # data_nascimento ausente -> 206
    }))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 200
    assert r.json()["parcial"] is True


# ── Mapeamento de erros do gateway ─────────────────────────────────────────

def test_cpf_nao_encontrado_404(api_client, mock_serpro):
    mock_serpro(_FakeResponse(404, {}))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 404


def test_cpf_cota_excedida_429(api_client, mock_serpro):
    mock_serpro(_FakeResponse(429, {}))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 429


def test_cpf_menor_de_idade_451(api_client, mock_serpro):
    """Motivo estruturado DV001 -> 451 Unavailable For Legal Reasons."""
    mock_serpro(_FakeResponse(422, {"motivo": "DV001", "mensagem": "Bloqueado"}))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 451
    assert "menor de idade" in r.json()["detail"].lower()


def test_cpf_422_generico_vira_502_com_diagnostico(api_client, mock_serpro):
    mock_serpro(_FakeResponse(422, {"mensagem": "campo invalido", "code": "E_VAL"}))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 502
    detail = r.json()["detail"]
    # Diagnostico deve incluir os campos seguros, sem ecoar o documento.
    assert "E_VAL" in detail or "campo invalido" in detail
    assert CPF_VALIDO.replace(".", "").replace("-", "") not in detail


def test_cpf_403_sem_motivo_vira_502(api_client, mock_serpro):
    mock_serpro(_FakeResponse(403, {}))
    r = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 502


# ── Validacao local: nao gasta cota ────────────────────────────────────────

def test_cpf_formato_curto_422_pydantic(api_client):
    r = api_client.post("/serpro/cpf", json={"cpf": "abc"})
    assert r.status_code == 422  # Pydantic ValidationError


def test_cnpj_dv_invalido_422_pydantic(api_client):
    r = api_client.post("/serpro/cnpj", json={"cnpj": "11.111.111/1111-11"})
    assert r.status_code == 422  # Pydantic ValidationError (DV)


def test_cpf_dv_invalido_400_local(api_client, mock_serpro):
    """CPF com 11 digitos mas DV errado: SerproDocumentoInvalido -> 400."""
    # Mock nao sera chamado — validacao local rejeita antes.
    mock_serpro(_FakeResponse(200, {}))
    r = api_client.post("/serpro/cpf", json={"cpf": "12345678900"})
    assert r.status_code == 400
    assert "invalido" in r.json()["detail"].lower() or "inválido" in r.json()["detail"].lower()


# ── Configuracao ausente -> 503 ────────────────────────────────────────────

def test_endpoints_503_sem_credenciais(monkeypatch):
    """Quando nem KEY/SECRET nem DEMO_TOKEN estao definidos, retorna 503."""
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_SECRET", raising=False)
    monkeypatch.delenv("ORGCONC_SERPRO_DEMO_TOKEN", raising=False)
    serpro_module._resetar_singleton_para_testes()
    c = TestClient(app)
    r = c.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r.status_code == 503
    r = c.post("/serpro/cnpj", json={"cnpj": CNPJ_VALIDO})
    assert r.status_code == 503


# ── Audit hook: garante hash determinístico e mascaramento ─────────────────

def test_audit_hook_emite_log_estruturado(api_client, mock_serpro, caplog):
    """O audit_hook deve emitir log JSON com documento_hash determinístico."""
    import logging
    caplog.set_level(logging.INFO, logger="orgconc.serpro")

    mock_serpro(_FakeResponse(200, {
        "nome": "X",
        "situacao": {"codigo": "0", "descricao": "Regular"},
    }))
    # Duas consultas do mesmo CPF -> mesmo hash de correlacao
    r1 = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    r2 = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r1.status_code == 200 and r2.status_code == 200

    audit_records = [
        rec for rec in caplog.records
        if rec.name == "orgconc.serpro" and getattr(rec, "audit_event", None) == "consulta_serpro"
    ]
    assert len(audit_records) >= 2
    hashes = [getattr(rec, "documento_hash", None) for rec in audit_records]
    assert hashes[0] is not None and hashes[0] == hashes[1], \
        f"hashes deveriam ser iguais para mesmo CPF+salt: {hashes}"
    # Mascaramento maximal: nenhum digito do CPF deve aparecer
    mascaras = {getattr(rec, "documento_mascarado", None) for rec in audit_records}
    assert mascaras == {"***.***.***-**"}
