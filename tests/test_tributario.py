"""Testes para api/matchers/tributario.py — estimativa IRPJ+CSLL + retenções."""
from __future__ import annotations


from api.matchers.conformidade import ConformidadeScore
from api.matchers.tributario import (
    ALIQUOTA_ICMS_ST,
    ALIQUOTA_IRPJ_CSLL,
    ALIQUOTA_RETENCAO_PJ,
    consolidar_risco,
    estimar_retencoes_nao_recolhidas,
    estimar_risco_fornecedor,
    estimar_risco_tributario_anual,
)


def _score(
    cnpj="11111111000111",
    volume_pago=100_000.0,
    volume_nf=0.0,
    classe="CRITICO",
    flags=None,
):
    return ConformidadeScore(
        cnpj_fornecedor=cnpj,
        razao_social="Forn",
        periodo_inicio=None,
        periodo_fim=None,
        volume_pago=volume_pago,
        volume_nf=volume_nf,
        conformidade_pct=0.0 if volume_nf == 0 else (volume_nf / volume_pago * 100),
        n_pagamentos=1,
        n_nfes=1 if volume_nf > 0 else 0,
        risco_classe=classe,
        flags=flags or [],
    )


def test_risco_zero_sem_gap():
    s = _score(volume_pago=1000, volume_nf=1000, classe="BAIXO")
    r = estimar_risco_fornecedor(s, meses_observados=5)
    assert r.risco_anual == 0.0
    assert "plena" in r.metodologia.lower()


def test_risco_irpj_csll_padrao():
    """100k pago em 5 meses sem NF → anualiza para 240k → 34% = 81.600."""
    s = _score(volume_pago=100_000, volume_nf=0, classe="CRITICO")
    r = estimar_risco_fornecedor(s, meses_observados=5)
    esperado_base = (100_000 / 5) * 12
    esperado_risco = esperado_base * ALIQUOTA_IRPJ_CSLL
    assert abs(r.base_calculo - esperado_base) < 0.01
    assert abs(r.risco_anual - esperado_risco) < 1.0


def test_risco_mei_sem_cte_adiciona_icms_st():
    s = _score(volume_pago=50_000, volume_nf=0, classe="CRITICO", flags=["MEI_SEM_CTE"])
    r = estimar_risco_fornecedor(s, meses_observados=5)
    # Aliquota deve incluir ICMS-ST
    assert r.aliquota_aplicada > ALIQUOTA_IRPJ_CSLL
    assert abs(r.aliquota_aplicada - (ALIQUOTA_IRPJ_CSLL + ALIQUOTA_ICMS_ST)) < 0.001
    assert "ICMS" in r.metodologia or "CT-e" in r.metodologia


def test_estimar_risco_tributario_anual_lote():
    scores = [
        _score(cnpj="aaa", volume_pago=100_000, volume_nf=0, classe="CRITICO"),
        _score(cnpj="bbb", volume_pago=50_000, volume_nf=50_000, classe="BAIXO"),
    ]
    riscos = estimar_risco_tributario_anual(scores, meses_observados=5)
    assert len(riscos) == 2
    # O segundo (com NF total) deve ter risco zero
    by_cnpj = {r.cnpj_fornecedor: r for r in riscos}
    assert by_cnpj["bbb"].risco_anual == 0
    assert by_cnpj["aaa"].risco_anual > 0


def test_estimar_retencoes_nao_recolhidas():
    r = estimar_retencoes_nao_recolhidas(
        volume_pago_pj=10_000_000, volume_pago_pf=0, meses_observados=5
    )
    base_anual_esperada = (10_000_000 / 5) * 12
    retencao_esperada = base_anual_esperada * ALIQUOTA_RETENCAO_PJ
    assert abs(r["base_pj_anual"] - base_anual_esperada) < 1.0
    assert abs(r["retencao_pj_anual"] - retencao_esperada) < 1.0
    assert r["total_anual"] == r["retencao_pj_anual"] + r["retencao_pf_anual"]


def test_consolidar_risco_top_n_e_por_classe():
    scores = [
        _score(cnpj=f"cnpj{i}", volume_pago=200_000 - i * 10_000, volume_nf=0, classe="CRITICO")
        for i in range(25)
    ]
    res = consolidar_risco(scores, meses_observados=5)
    assert res["total_anual"] > 0
    assert "CRITICO" in res["por_classe_risco"]
    assert len(res["top_fornecedores"]) <= 20


def test_meses_observados_zero_nao_explode():
    s = _score(volume_pago=100, volume_nf=0)
    r = estimar_risco_fornecedor(s, meses_observados=0)
    # Garante que não há divisão por zero
    assert r.risco_anual >= 0
