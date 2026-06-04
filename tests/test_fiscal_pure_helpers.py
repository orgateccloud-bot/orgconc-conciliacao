"""Cobertura de funções puras fiscais subtestadas: segurança (SMTP header
injection), classificação de conformidade e validadores Pydantic dos routers.

Tudo determinístico, sem DB/rede — alvos de baixo esforço e alto valor.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from api.matchers.conformidade import (
    ConformidadeScore,
    _classe,
    _detectar_flags,
    classificar_risco,
)
from api.routers.contratos import ContratoCreate
from api.routers.guias import GuiaCreate
from api.services.fiscal_notifications import _sanitize_header


# ── _sanitize_header — prevenção de SMTP header injection (segurança) ──
def test_sanitize_header_neutraliza_crlf():
    out = _sanitize_header("Assunto\r\nBcc: attacker@evil.com")
    assert "\r" not in out and "\n" not in out
    assert "Bcc:" in out  # conteúdo preservado; só os controles viram espaço


def test_sanitize_header_neutraliza_tab():
    assert "\t" not in _sanitize_header("col\ttab")


def test_sanitize_header_trunca_em_200():
    assert len(_sanitize_header("x" * 500)) == 200


def test_sanitize_header_vazio_ou_none():
    assert _sanitize_header("") == ""
    assert _sanitize_header(None) == ""  # type: ignore[arg-type]


# ── _classe — limiares de conformidade (incl. fronteiras) ─────────────
@pytest.mark.parametrize("pct,esperado", [
    (100.0, "BAIXO"), (80.0, "BAIXO"), (79.99, "MEDIO"),
    (50.0, "MEDIO"), (49.99, "ALTO"), (20.0, "ALTO"),
    (19.99, "CRITICO"), (0.0, "CRITICO"),
])
def test_classe_limiares(pct, esperado):
    assert _classe(pct) == esperado


# ── _detectar_flags — cobertura de cada branch de flag ────────────────
def test_flag_rede_frota_volume_alto_sem_nf():
    flags = _detectar_flags(nome="REDE FROTA", cnae="", volume_pago=120_000,
                            volume_nf=0, is_mei=False, n_ctes=0)
    assert "REDE_FROTA_TYPE" in flags


def test_sem_rede_frota_quando_ha_nf():
    flags = _detectar_flags(nome="X", cnae="", volume_pago=120_000,
                            volume_nf=50_000, is_mei=False, n_ctes=0)
    assert "REDE_FROTA_TYPE" not in flags


def test_flag_mei_sem_cte():
    flags = _detectar_flags(nome="MEI", cnae="4930-2/02", volume_pago=10_000,
                            volume_nf=0, is_mei=True, n_ctes=0)
    assert "MEI_SEM_CTE" in flags


def test_mei_com_cte_nao_flaga():
    flags = _detectar_flags(nome="MEI", cnae="4930-2/02", volume_pago=10_000,
                            volume_nf=0, is_mei=True, n_ctes=3)
    assert "MEI_SEM_CTE" not in flags


def test_mei_cnae_fora_de_transporte_nao_flaga():
    flags = _detectar_flags(nome="MEI", cnae="6201-5/00", volume_pago=10_000,
                            volume_nf=0, is_mei=True, n_ctes=0)
    assert "MEI_SEM_CTE" not in flags


def test_flag_parte_relacionada_via_nome_socio():
    flags = _detectar_flags(nome="JOAO SILVA VEICULOS LTDA", cnae="", volume_pago=1000,
                            volume_nf=0, is_mei=False, n_ctes=0, nomes_socios=["Joao Silva"])
    assert "PARTE_RELACIONADA" in flags


def test_sem_socio_nao_dispara_parte_relacionada():
    flags = _detectar_flags(nome="EXEMPLO AGRO LTDA", cnae="", volume_pago=1000,
                            volume_nf=0, is_mei=False, n_ctes=0, nomes_socios=["Joao Silva"])
    assert "PARTE_RELACIONADA" not in flags


def test_flag_parte_relacionada_via_socio():
    flags = _detectar_flags(nome="JOAO SILVA TRANSPORTES", cnae="", volume_pago=1000,
                            volume_nf=0, is_mei=False, n_ctes=0, nomes_socios=["Joao Silva"])
    assert "PARTE_RELACIONADA" in flags


def test_multiplas_flags_simultaneas():
    flags = _detectar_flags(nome="JOAO SILVA MEI", cnae="4930-2/02", volume_pago=120_000,
                            volume_nf=0, is_mei=True, n_ctes=0, nomes_socios=["Joao Silva"])
    assert {"REDE_FROTA_TYPE", "MEI_SEM_CTE", "PARTE_RELACIONADA"} <= set(flags)


def test_caso_limpo_sem_flags():
    flags = _detectar_flags(nome="FORNECEDOR OK", cnae="", volume_pago=5000,
                            volume_nf=5000, is_mei=False, n_ctes=0)
    assert flags == []


# ── classificar_risco — override por flag crítica ─────────────────────
def _score(classe="MEDIO", flags=None):
    return ConformidadeScore(
        cnpj_fornecedor="1", razao_social="X", periodo_inicio=None, periodo_fim=None,
        volume_pago=1.0, volume_nf=0.0, conformidade_pct=0.0, n_pagamentos=1,
        n_nfes=0, risco_classe=classe, flags=flags or [],
    )


def test_classificar_risco_rede_frota_forca_critico():
    assert classificar_risco(_score(classe="BAIXO", flags=["REDE_FROTA_TYPE"])) == "CRITICO"


def test_classificar_risco_mei_forca_critico():
    assert classificar_risco(_score(classe="MEDIO", flags=["MEI_SEM_CTE"])) == "CRITICO"


def test_classificar_risco_sem_flags_passthrough():
    assert classificar_risco(_score(classe="ALTO", flags=[])) == "ALTO"


def test_classificar_risco_flag_nao_critica_passthrough():
    assert classificar_risco(_score(classe="BAIXO", flags=["PARTE_RELACIONADA"])) == "BAIXO"


# ── Validadores Pydantic dos routers (contratos / guias) ──────────────
# ValidationError herda de ValueError; pytest.raises(ValueError) cobre tanto
# erro de campo (gt=0) quanto erro levantado em model_post_init.
def test_contrato_periodicidade_normalizada():
    c = ContratoCreate(cliente_id=uuid.uuid4(), descricao="Aluguel",
                       valor=Decimal("1500"), periodicidade="MENSAL")
    assert c.periodicidade == "mensal"


def test_contrato_periodicidade_invalida_rejeitada():
    with pytest.raises(ValueError):
        ContratoCreate(cliente_id=uuid.uuid4(), descricao="X",
                       valor=Decimal("10"), periodicidade="quinzenal")


def test_contrato_valor_deve_ser_positivo():
    with pytest.raises(ValueError):
        ContratoCreate(cliente_id=uuid.uuid4(), descricao="X",
                       valor=Decimal("0"), periodicidade="mensal")


def test_guia_tipo_normalizado():
    g = GuiaCreate(cliente_id=uuid.uuid4(), tipo="darf", valor=Decimal("250"))
    assert g.tipo == "DARF"


def test_guia_tipo_invalido_rejeitado():
    with pytest.raises(ValueError):
        GuiaCreate(cliente_id=uuid.uuid4(), tipo="XYZ", valor=Decimal("10"))


def test_guia_valor_deve_ser_positivo():
    with pytest.raises(ValueError):
        GuiaCreate(cliente_id=uuid.uuid4(), tipo="DAS", valor=Decimal("0"))
