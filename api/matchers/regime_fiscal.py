"""Análise de compatibilidade de regime tributário — múltiplo do teto.

Achado CENTRAL da auditoria bancária forense (metodologia OrgAudi), que o
cruzamento doc×pagamento não captura: comparar o volume bruto **anualizado**
movimentado na conta com o **teto do regime tributário** declarado.

Um EPP (teto R$ 4,8M/ano) movimentando ~R$ 187M/ano = ~39× o teto é o sinal nº 1
de incompatibilidade de regime — indício de caixa dois, interposição de pessoas
ou enquadramento incorreto. É determinístico e barato: anualiza o volume e divide
pelo teto.

Base legal: LC 123/2006 (Simples Nacional / EPP / MEI) e atualizações.
"""
from __future__ import annotations

from dataclasses import dataclass

# Tetos de receita bruta anual (R$) — LC 123/2006
TETO_MEI = 81_000.0
TETO_SIMPLES_EPP = 4_800_000.0  # EPP / Simples Nacional (sublimite/limite)

# Limiares de múltiplo do teto → classe de risco
_LIM_ATENCAO = 1.0   # acima do teto
_LIM_ALTO = 3.0
_LIM_CRITICO = 10.0


@dataclass
class AnaliseRegime:
    volume_bruto: float
    meses_observados: float
    volume_anualizado: float
    teto: float
    multiplo_do_teto: float
    classe: str          # COMPATIVEL | ATENCAO | ALTO | CRITICO
    incompativel: bool


def analisar_regime(
    volume_credito: float,
    volume_debito: float,
    meses_observados: float,
    teto: float = TETO_SIMPLES_EPP,
) -> AnaliseRegime:
    """Anualiza o volume bruto (créditos + |débitos|) e compara com o teto.

    `meses_observados` pode ser fracionário (ex.: 4,5 meses). `volume_debito` é
    tipicamente negativo no extrato; usamos o valor absoluto.
    """
    volume_bruto = abs(volume_credito) + abs(volume_debito)
    meses = meses_observados if meses_observados and meses_observados > 0 else 1.0
    anualizado = (volume_bruto / meses) * 12.0
    multiplo = anualizado / teto if teto > 0 else 0.0

    if multiplo <= _LIM_ATENCAO:
        classe = "COMPATIVEL"
    elif multiplo <= _LIM_ALTO:
        classe = "ATENCAO"
    elif multiplo <= _LIM_CRITICO:
        classe = "ALTO"
    else:
        classe = "CRITICO"

    return AnaliseRegime(
        volume_bruto=round(volume_bruto, 2),
        meses_observados=round(meses, 2),
        volume_anualizado=round(anualizado, 2),
        teto=teto,
        multiplo_do_teto=round(multiplo, 2),
        classe=classe,
        incompativel=multiplo > _LIM_ATENCAO,
    )
