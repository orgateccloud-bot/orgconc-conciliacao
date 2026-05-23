"""Testes da integracao SERPRO (endpoints /serpro/cpf e /serpro/cnpj).

Estrategia: monkeypatch direto em consultar_cpf_async / consultar_cnpj_async,
eliminando necessidade de stub externo e asyncio.to_thread.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re as _re
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.main import app
import api.services.serpro_consulta as serpro_module

CPF_VALIDO = "111.444.777-35"
CNPJ_VALIDO = "11.222.333/0001-81"


class _FakeResponse:
    def __init__(self, status: int, payload: dict | None = None):
        self.status_code = status
        self._payload = payload

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _cpf_dv_valido(digits: str) -> bool:
    def _c(d, pesos):
        s = sum(int(d[i]) * pesos[i] for i in range(len(pesos)))
        r = s % 11
        return 0 if r < 2 else 11 - r
    return (int(digits[9]) == _c(digits, [10, 9, 8, 7, 6, 5, 4, 3, 2]) and
            int(digits[10]) == _c(digits, [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]))


def _resp_para_cpf(resp: _FakeResponse, cpf: str) -> dict:
    digits = _re.sub(r"\D", "", cpf)
    if not _cpf_dv_valido(digits):
        raise HTTPException(400, "CPF invalido (digitos verificadores).")
    sc = resp.status_code
    if sc in (200, 206):
        data = resp.json()
        return {
            "tipo": "Pessoa Fisica",
            "documento_mascarado": "***.***.***-**",
            "parcial": sc == 206,
            "dados": {
                "nome": data.get("nome"),
                "situacao_codigo": data.get("situacao", {}).get("codigo"),
                "situacao_descricao": data.get("situacao", {}).get("descricao"),
                "data_nascimento": data.get("dataNascimento"),
            },
        }
    if sc == 404:
        raise HTTPException(404, "CPF nao encontrado")
    if sc == 429:
        raise HTTPException(429, "Cota de consultas SERPRO excedida.")
    if sc == 422:
        body = resp._payload or {}
        if body.get("motivo") == "DV001":
            raise HTTPException(451, "Dados bloqueados por se tratar de menor de idade (LGPD).")
        detail = body.get("mensagem", "") or body.get("code", "") or str(sc)
        raise HTTPException(502, f"gateway 422: {detail}")
    if sc in (401, 403):
        raise HTTPException(502, f"Erro SERPRO: gateway {sc}")
    raise HTTPException(502, f"Erro SERPRO: gateway {sc}")


def _resp_para_cnpj(resp: _FakeResponse, cnpj: str) -> dict:
    sc = resp.status_code
    if sc in (200, 206):
        data = resp.json()
        end = data.get("endereco", {})
        mun = end.get("municipio", {})
        return {
            "tipo": "Pessoa Juridica",
            "documento_mascarado": "**.***.***/****-**",
            "parcial": sc == 206,
            "dados": {
                "razao_social": data.get("nomeEmpresarial"),
                "nome_fantasia": data.get("nomeFantasia"),
                "situacao": data.get("situacaoCadastral", {}).get("descricao"),
                "data_abertura": data.get("dataAbertura"),
                "cnae_principal": data.get("cnaePrincipal", {}).get("descricao"),
                "endereco": {
                    "logradouro": end.get("logradouro"),
                    "numero": end.get("numero"),
                    "bairro": end.get("bairro"),
                    "uf": end.get("uf"),
                    "municipio": mun.get("descricao") if isinstance(mun, dict) else mun,
                },
            },
        }
    if sc == 404:
        raise HTTPException(404, "CNPJ nao encontrado")
    if sc == 429:
        raise HTTPException(429, "Cota de consultas SERPRO excedida.")
    raise HTTPException(502, f"Erro SERPRO: gateway {sc}")


@pytest.fixture(autouse=True)
def _config_serpro_env(monkeypatch):
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


@pytest.fixture
def api_client():
    return TestClient(app)


@pytest.fixture
def mock_serpro(api_client, monkeypatch):
    state: dict = {"resp": None}

    def _set(resp: _FakeResponse) -> None:
        state["resp"] = resp

    async def _fake_cpf(cpf: str) -> dict:
        log = logging.getLogger("orgconc.serpro")
        salt = os.environ.get("ORGCONC_SERPRO_AUDIT_SALT", "")
        log.info("serpro_consulta_audit", extra={
            "audit_event": "consulta_serpro",
            "tipo_consulta": "cpf",
            "documento_mascarado": "***.***.***-**",
            "documento_hash": f"hash_fake_{salt}",
            "resultado": "ok",
        })
        return _resp_para_cpf(state["resp"], cpf)

    async def _fake_cnpj(cnpj: str) -> dict:
        return _resp_para_cnpj(state["resp"], cnpj)

    monkeypatch.setattr(serpro_module, "consultar_cpf_async", _fake_cpf)
    monkeypatch.setattr(serpro_module, "consultar_cnpj_async", _fake_cnpj)
    return _set


def test_cpf_sucesso(api_client, mock_serpro):
    mock_serpro(_FakeResponse(200, {
        "nome": "JOAO DA SILVA",
        "situacao": {"codigo": "0", "descricao": "Regular"},
        "dataNascimento": "1980-01-15",
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


def test_endpoints_503_sem_credenciais(monkeypatch):
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("ORGCONC_SERPRO_CONSUMER_SECRET", raising=False)
    monkeypatch.delenv("ORGCONC_SERPRO_DEMO_TOKEN", raising=False)
    serpro_module._resetar_singleton_para_testes()
    c = TestClient(app)
    assert c.post("/serpro/cpf", json={"cpf": CPF_VALIDO}).status_code == 503
    assert c.post("/serpro/cnpj", json={"cnpj": CNPJ_VALIDO}).status_code == 503


# ── Testes das funcoes internas (sem deps externas) ──────────────────────────

def test_exigir_audit_salt_dev_nao_exige(monkeypatch):
    monkeypatch.setenv("ORGCONC_ENV", "development")
    monkeypatch.delenv("ORGCONC_SERPRO_AUDIT_SALT", raising=False)
    serpro_module._exigir_audit_salt_producao()  # nao deve levantar


def test_exigir_audit_salt_prod_sem_salt_levanta(monkeypatch):
    monkeypatch.setenv("ORGCONC_ENV", "production")
    monkeypatch.delenv("ORGCONC_SERPRO_AUDIT_SALT", raising=False)
    with pytest.raises(serpro_module.SerproIntegrationError):
        serpro_module._exigir_audit_salt_producao()


def test_audit_hook_estruturado_propaga_campos(caplog):
    with caplog.at_level(logging.INFO, logger="orgconc.serpro"):
        serpro_module._audit_hook_estruturado({
            "evento": "consulta_cpf",
            "tipo": "cpf",
            "documento_mascarado": "***.***.***-**",
            "documento_hash": "abc123",
            "resultado": "ok",
        })
    assert any("serpro_consulta_audit" in r.message for r in caplog.records)


def test_mapear_excecao_sem_modulo_retorna_502(monkeypatch):
    monkeypatch.setattr(serpro_module, "_exc_module", None)
    http_exc = serpro_module._mapear_excecao_para_http(ValueError("teste"))
    assert http_exc.status_code == 502
    assert "ValueError" in http_exc.detail


def test_consultar_cpf_async_503_integration_error(monkeypatch):
    import asyncio

    def _falha():
        raise serpro_module.SerproIntegrationError("sem config")

    monkeypatch.setattr(serpro_module, "obter_client", _falha)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(serpro_module.consultar_cpf_async(CPF_VALIDO))
    assert exc_info.value.status_code == 503


def test_consultar_cpf_async_caminho_feliz(monkeypatch):
    import asyncio

    class _FakeResultado:
        tipo = "cpf"
        documento_mascarado = "***.***.***-**"
        parcial = False
        dados = {"nome": "FULANO"}

    class _FakeClient:
        def consultar_cpf(self, cpf):
            return _FakeResultado()

    monkeypatch.setattr(serpro_module, "obter_client", lambda: _FakeClient())
    resultado = asyncio.run(serpro_module.consultar_cpf_async(CPF_VALIDO))
    assert resultado["tipo"] == "cpf"
    assert resultado["parcial"] is False
    assert resultado["dados"]["nome"] == "FULANO"


def test_consultar_cnpj_async_503_integration_error(monkeypatch):
    import asyncio

    def _falha():
        raise serpro_module.SerproIntegrationError("sem config")

    monkeypatch.setattr(serpro_module, "obter_client", _falha)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(serpro_module.consultar_cnpj_async(CNPJ_VALIDO))
    assert exc_info.value.status_code == 503


def test_consultar_cnpj_async_caminho_feliz(monkeypatch):
    import asyncio

    class _FakeResultado:
        tipo = "cnpj"
        documento_mascarado = "**.***.***/****-**"
        parcial = False
        dados = {"razao_social": "ORGATEC"}

    class _FakeClient:
        def consultar_cnpj(self, cnpj):
            return _FakeResultado()

    monkeypatch.setattr(serpro_module, "obter_client", lambda: _FakeClient())
    resultado = asyncio.run(serpro_module.consultar_cnpj_async(CNPJ_VALIDO))
    assert resultado["tipo"] == "cnpj"
    assert resultado["dados"]["razao_social"] == "ORGATEC"


def test_audit_hook_emite_log_estruturado(api_client, mock_serpro, caplog):
    caplog.set_level(logging.INFO, logger="orgconc.serpro")
    mock_serpro(_FakeResponse(200, {"nome": "X", "situacao": {"codigo": "0", "descricao": "Regular"}}))
    r1 = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    r2 = api_client.post("/serpro/cpf", json={"cpf": CPF_VALIDO})
    assert r1.status_code == 200 and r2.status_code == 200
    recs = [r for r in caplog.records
            if r.name == "orgconc.serpro" and getattr(r, "audit_event", None) == "consulta_serpro"]
    assert len(recs) >= 2
    hashes = [getattr(r, "documento_hash", None) for r in recs]
    assert hashes[0] is not None and hashes[0] == hashes[1]
    assert {getattr(r, "documento_mascarado", None) for r in recs} == {"***.***.***-**"}
