"""Estimativa de risco tributário para Lucro Real.

Sprint 2 do Plano de Integração Fiscal.

Premissas:
- IRPJ 25% + CSLL 9% = 34% sobre despesa indedutível
- PIS+COFINS+CSLL+IRRF retidos: 6,15% (PJ serviços)
- IRRF PF autônomo: até 27,5%
- INSS retido PF: 11%
- ICMS-ST (transporte sem CT-e): ~5%

Modelo de cálculo:
- Pagamento sem NF-e (RIR/2018 art. 311) → despesa indedutível → 34% LALUR
- Pagamento a MEI caminhoneiro sem CT-e → IRPJ+CSLL adicional + ICMS-ST
- Retenção não recolhida → multa 75-150% + juros SELIC

ATENÇÃO — VIGÊNCIA DAS ALÍQUOTAS:
- ALIQUOTA_IRPJ_CSLL: vigente conforme RIR/2018 (sem alteração até 2025-06)
- ALIQUOTA_ICMS_ST: estimativa média nacional; varia por UF e NCM.
  SP ~18%, MG ~7%, CE ~0%. Usar tabela por UF/produto para precisão.
- ALIQUOTA_RETENCAO_PJ: mix simplificado. Reforma Tributária (PL 68/2024)
  altera CBS/IBS a partir de 2026 — revisar antes da entrada em vigor.
- Todas as alíquotas têm data de última verificação: 2025-06.
  Acrescentar teste automatizado de vigência ou revisar a cada trimestre.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from api.matchers.conformidade import ConformidadeScore

# Vigência verificada em 2025-06. Revisar trimestralmente.
ALIQUOTA_IRPJ_CSLL = 0.34      # 25% IRPJ + 9% CSLL — RIR/2018
ALIQUOTA_ICMS_ST = 0.05        # estimativa média; varia por UF/NCM
ALIQUOTA_RETENCAO_PJ = 0.0615  # PIS+COFINS+CSLL+IRRF retidos (serviços)
ALIQUOTA_RETENCAO_PF = 0.275   # IRRF máximo PF autônomo
ALIQUOTA_INSS_PF = 0.11


def _dec(v: float) -> Decimal:
    return Decimal(str(v))


def _round2(d: Decimal) -> float:
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass
class RiscoTributario:
    cnpj_fornecedor: str
    razao_social: str
    base_calculo: float
    aliquota_aplicada: float
    risco_anual: float
    metodologia: str


def _anualizar(valor: float, meses_observados: int = 5) -> float:
    """Projeta valor mensal × 12 a partir de N meses observados."""
    if meses_observados <= 0:
        return valor
    return (valor / meses_observados) * 12.0


def estimar_risco_fornecedor(
    score: ConformidadeScore,
    meses_observados: int = 5,
) -> RiscoTributario:
    """Calcula risco anual para 1 fornecedor com base no score de conformidade."""
    gap_pagamento = score.volume_pago - score.volume_nf
    gap_pagamento = max(gap_pagamento, 0)  # se NF > pagamento, sem gap

    if gap_pagamento <= 0:
        return RiscoTributario(
            cnpj_fornecedor=score.cnpj_fornecedor,
            razao_social=score.razao_social,
            base_calculo=0.0,
            aliquota_aplicada=0.0,
            risco_anual=0.0,
            metodologia="Conformidade plena",
        )

    base_anual = _anualizar(gap_pagamento, meses_observados)
    aliquota = ALIQUOTA_IRPJ_CSLL
    metodologia = "IRPJ+CSLL sobre despesa indedutível (RIR 311)"

    if "MEI_SEM_CTE" in score.flags:
        aliquota += ALIQUOTA_ICMS_ST
        metodologia = "IRPJ+CSLL+ICMS-ST (Decreto 8.324/2014)"

    base_dec = _dec(base_anual)
    risco_dec = base_dec * _dec(aliquota)
    return RiscoTributario(
        cnpj_fornecedor=score.cnpj_fornecedor,
        razao_social=score.razao_social,
        base_calculo=_round2(base_dec),
        aliquota_aplicada=round(aliquota, 4),
        risco_anual=_round2(risco_dec),
        metodologia=metodologia,
    )


def estimar_risco_tributario_anual(
    scores: Iterable[ConformidadeScore],
    meses_observados: int = 5,
) -> list[RiscoTributario]:
    """Calcula risco anual para todos os fornecedores."""
    return [estimar_risco_fornecedor(s, meses_observados) for s in scores]


def estimar_retencoes_nao_recolhidas(
    volume_pago_pj: float,
    volume_pago_pf: float,
    meses_observados: int = 5,
) -> dict:
    """Estima retenções não recolhidas (PIS+COFINS+CSLL+IRRF+INSS).

    Retorna dict com bases e alíquotas anualizadas.
    """
    base_pj_anual = _anualizar(volume_pago_pj, meses_observados)
    base_pf_anual = _anualizar(volume_pago_pf, meses_observados)
    pj_dec = _dec(base_pj_anual)
    pf_dec = _dec(base_pf_anual)
    retencao_pj_dec = pj_dec * _dec(ALIQUOTA_RETENCAO_PJ)
    retencao_pf_dec = pf_dec * (_dec(ALIQUOTA_RETENCAO_PF) + _dec(ALIQUOTA_INSS_PF)) / _dec(2)
    return {
        "base_pj_anual": _round2(pj_dec),
        "base_pf_anual": _round2(pf_dec),
        "retencao_pj_anual": _round2(retencao_pj_dec),
        "retencao_pf_anual": _round2(retencao_pf_dec),
        "total_anual": _round2(retencao_pj_dec + retencao_pf_dec),
        "aliquotas": {
            "pj_servicos_pct": ALIQUOTA_RETENCAO_PJ * 100,
            "pf_irrf_max_pct": ALIQUOTA_RETENCAO_PF * 100,
            "pf_inss_pct": ALIQUOTA_INSS_PF * 100,
        },
    }


def consolidar_risco(
    scores: Iterable[ConformidadeScore],
    meses_observados: int = 5,
) -> dict:
    """Consolida risco total por classe e por flag, e gera ranking top-N."""
    riscos = estimar_risco_tributario_anual(scores, meses_observados)
    score_by_cnpj = {s.cnpj_fornecedor: s for s in scores}
    por_classe: dict[str, float] = {"BAIXO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 0}
    por_flag: dict[str, float] = {}
    for r in riscos:
        s = score_by_cnpj.get(r.cnpj_fornecedor)
        if not s:
            continue
        por_classe[s.risco_classe] = por_classe.get(s.risco_classe, 0) + r.risco_anual
        for flag in s.flags:
            por_flag[flag] = por_flag.get(flag, 0) + r.risco_anual
    riscos_sorted = sorted(riscos, key=lambda x: -x.risco_anual)[:20]
    return {
        "total_anual": round(sum(r.risco_anual for r in riscos), 2),
        "por_classe_risco": {k: round(v, 2) for k, v in por_classe.items()},
        "por_flag": {k: round(v, 2) for k, v in por_flag.items()},
        "top_fornecedores": [
            {
                "cnpj": r.cnpj_fornecedor,
                "razao_social": r.razao_social,
                "base_calculo": r.base_calculo,
                "risco_anual": r.risco_anual,
                "metodologia": r.metodologia,
            } for r in riscos_sorted
        ],
    }
