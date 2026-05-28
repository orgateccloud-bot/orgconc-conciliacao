"""Testes para api/matchers/conformidade.py — score + flags."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from api.matchers.conformidade import (
    ConformidadeScore,
    _classe,
    _detectar_flags,
    calcular_conformidade_fornecedor,
    classificar_risco,
)
from api.matchers.xml_fiscal import DocumentoFiscalLido


@dataclass
class _Tx:
    data: date
    valor: float
    nome: str = ""
    memo: str = ""
    fitid: str = ""
    tipo: str = "DEBIT"


def _doc(emit_cnpj="12345678000190", valor=1000.0, tipo="NF-e"):
    return DocumentoFiscalLido(
        tipo=tipo, modelo="55", chave="x" * 44, numero="1", serie="1",
        data_emissao="2026-04-15", emit_cnpj=emit_cnpj, emit_nome="Forn",
        emit_uf="GO", dest_cnpj="", dest_nome="", valor_total=valor,
    )


# ────────────────────────────────────────────────────────────────────────
# _classe e _detectar_flags
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("pct,esperado", [
    (100, "BAIXO"),
    (85, "BAIXO"),
    (80, "BAIXO"),
    (79, "MEDIO"),
    (50, "MEDIO"),
    (49, "ALTO"),
    (20, "ALTO"),
    (19, "CRITICO"),
    (0, "CRITICO"),
])
def test_classe_buckets(pct, esperado):
    assert _classe(pct) == esperado


def test_flag_rede_frota_type():
    flags = _detectar_flags(
        nome="REDE FROTA SOLUTIONS", cnae="6619", volume_pago=200_000,
        volume_nf=0, is_mei=False, n_ctes=0,
    )
    assert "REDE_FROTA_TYPE" in flags


def test_flag_mei_sem_cte():
    flags = _detectar_flags(
        nome="JOAO CAMINHONEIRO", cnae="4930-2", volume_pago=50_000,
        volume_nf=50_000, is_mei=True, n_ctes=0,
    )
    assert "MEI_SEM_CTE" in flags


def test_flag_mei_com_cte_nao_dispara():
    flags = _detectar_flags(
        nome="JOAO CAMINHONEIRO", cnae="4930-2", volume_pago=50_000,
        volume_nf=50_000, is_mei=True, n_ctes=3,
    )
    assert "MEI_SEM_CTE" not in flags


def test_flag_parte_relacionada_heuristica_locar():
    flags = _detectar_flags(
        nome="LOCAR LOCADORA E TRANSPORTES", cnae="", volume_pago=100,
        volume_nf=100, is_mei=False, n_ctes=0,
    )
    assert "PARTE_RELACIONADA" in flags


def test_flag_parte_relacionada_por_socio():
    flags = _detectar_flags(
        nome="RENATO COSTA TRANSPORTES", cnae="", volume_pago=100,
        volume_nf=100, is_mei=False, n_ctes=0,
        nomes_socios=["Renato Costa"],
    )
    assert "PARTE_RELACIONADA" in flags


def test_locar_bovinos_nao_dispara_parte_relacionada():
    """A própria empresa auditada (LOCAR BOVINOS) não deve cair em parte relacionada."""
    flags = _detectar_flags(
        nome="LOCAR TRANSPORTE DE BOVINOS LTDA", cnae="", volume_pago=100,
        volume_nf=100, is_mei=False, n_ctes=0,
    )
    assert "PARTE_RELACIONADA" not in flags


# ────────────────────────────────────────────────────────────────────────
# calcular_conformidade_fornecedor
# ────────────────────────────────────────────────────────────────────────


def test_score_100_quando_pagamento_e_nf_iguais():
    docs = [_doc(emit_cnpj="12345678000190", valor=1500.0)]
    txs = [_Tx(data=date(2026, 4, 16), valor=-1500.0, nome="FORN 12.345.678/0001-90")]
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert len(scores) == 1
    assert scores[0].conformidade_pct >= 99.9
    assert scores[0].risco_classe == "BAIXO"


def test_score_zero_quando_paga_sem_nf():
    docs = []
    txs = [_Tx(data=date(2026, 4, 16), valor=-200_000.0, nome="REDE FROTA 24.478.438/0001-48")]
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert len(scores) == 1
    assert scores[0].conformidade_pct == 0.0
    assert scores[0].risco_classe == "CRITICO"
    assert "REDE_FROTA_TYPE" in scores[0].flags


def test_score_parcial_metade():
    docs = [_doc(emit_cnpj="12345678000190", valor=500.0)]
    txs = [_Tx(data=date(2026, 4, 16), valor=-1000.0, nome="X 12.345.678/0001-90")]
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert 49.0 < scores[0].conformidade_pct < 51.0
    assert scores[0].risco_classe in ("MEDIO", "ALTO")


def test_classificar_risco_eleva_para_critico_com_flag():
    """A presença de REDE_FROTA_TYPE ou MEI_SEM_CTE deve forçar CRITICO."""
    score = ConformidadeScore(
        cnpj_fornecedor="111", razao_social="x", periodo_inicio=None, periodo_fim=None,
        volume_pago=100, volume_nf=100, conformidade_pct=100, n_pagamentos=1,
        n_nfes=1, risco_classe="BAIXO", flags=["REDE_FROTA_TYPE"],
    )
    assert classificar_risco(score) == "CRITICO"


def test_score_sem_pagamento_mas_com_nf():
    """Documento emitido sem pagamento OFX correspondente — conformidade 100% (tem documento)."""
    docs = [_doc(emit_cnpj="12345678000190", valor=1000.0)]
    txs = []
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert scores[0].conformidade_pct == 100.0
    assert scores[0].risco_classe == "BAIXO"
