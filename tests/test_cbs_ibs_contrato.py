"""Teste de contrato IC-02 (§9.2) — Calculadora CBS/IBS.

Valida, em cada build:
1. Os exemplos do contrato (request/response) contra os JSON Schemas.
2. Que a saída de POST /fiscal/apurar (stub PILOTO) respeita o schema de saída,
   o gate de proveniência (§4), a memória por esfera (§5) e a aritmética.
3. Que o payload_hash é determinístico e canônico.
4. Que modos != stub exigem integração SERPRO (Fase 1).
"""
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("CALCULADORA_MODO", "stub")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.main import app

client = TestClient(app)
FIX = Path(__file__).resolve().parent / "fixtures" / "ic_02"


def _load(nome: str) -> dict:
    return json.loads((FIX / nome).read_text(encoding="utf-8"))


SCHEMA_IN = _load("operacao_fiscal_input.schema.json")
SCHEMA_OUT = _load("apuracao_cbs_ibs.schema.json")
REQ = _load("exemplo_request.json")
RESP = _load("exemplo_response.json")


def test_exemplos_validam_contra_schemas():
    import jsonschema
    jsonschema.validate(REQ, SCHEMA_IN)
    jsonschema.validate(RESP, SCHEMA_OUT)


def test_apurar_endpoint_respeita_contrato_e_gate():
    import jsonschema
    r = client.post("/fiscal/apurar", json=REQ)
    assert r.status_code == 200, r.text
    j = r.json()

    # 1) Saída respeita o JSON Schema do contrato IC-02 §3.2.
    jsonschema.validate(j, SCHEMA_OUT)

    # 2) Gate de proveniência (§4) + memória por esfera (§5).
    assert j["versao_base"]
    assert j["ambiente"] in ("PILOTO", "PRODUCAO")
    assert j["fundamentacao_legal"]
    for g in ("gIBSUF", "gIBSMun", "gCBS"):
        assert j[g]["memoriaCalculo"].strip()

    # 3) Eco do documento + aritmética (base 200 → soma das esferas == vTotTrib).
    assert j["documento_id"] == REQ["documento_id"]
    assert j["base_calculo_total"] == 200.0
    soma = round(j["gIBSUF"]["vIBSUF"] + j["gIBSMun"]["vIBSMun"] + j["gCBS"]["vCBS"], 2)
    assert abs(soma - j["vTotTrib"]) < 0.005


def test_payload_hash_deterministico_e_canonico():
    from api.schemas_cbs_ibs import OperacaoFiscalInput
    from api.services.calculadora_cbs_ibs import payload_hash_de
    h1 = payload_hash_de(OperacaoFiscalInput(**REQ))
    h2 = payload_hash_de(OperacaoFiscalInput(**REQ))
    assert h1 == h2
    assert len(h1) == 64 and all(c in "0123456789abcdef" for c in h1)


def test_input_exige_xml_ou_itens():
    from api.schemas_cbs_ibs import OperacaoFiscalInput
    with pytest.raises(ValueError):
        OperacaoFiscalInput(
            documento_id="x", uf="GO", municipio_ibge="5208707",
            data_fato_gerador="2026-05-29",
        )


@pytest.mark.asyncio
async def test_modo_nao_stub_exige_calculadora_url(monkeypatch):
    # Modo hospedada/offline despacha p/ a Calculadora oficial (RTC, sem auth).
    # Sem CALCULADORA_BASE_URL, levanta CalculadoraConfigError — o mapeamento
    # IC-02↔RTC já está implementado (não é mais NotImplementedError).
    from api.core import config
    from api.schemas_cbs_ibs import OperacaoFiscalInput
    from api.services import calculadora_cbs_ibs
    from api.services.calculadora_client import CalculadoraConfigError
    monkeypatch.setattr(config, "CALCULADORA_MODO", "hospedada")
    monkeypatch.setattr(config, "CALCULADORA_BASE_URL", "")
    with pytest.raises(CalculadoraConfigError):
        await calculadora_cbs_ibs.apurar(OperacaoFiscalInput(**REQ))
