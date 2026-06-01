"""Golden tests do múltiplo do teto — ancorados no laudo REAL validado (não-circular).

O caso de referência (auditoria bancária forense validada por contador) movimentou
R$ 35,2M de créditos + R$ 35,05M de débitos em 4,5 meses → R$ 187,3M anualizado =
~39× o teto EPP (R$ 4,8M). Esses números vêm do laudo-verdade, não da ferramenta.
"""
from __future__ import annotations

from api.matchers.regime_fiscal import (
    TETO_MEI,
    analisar_regime,
)


def test_caso_referencia_epp_39x_critico():
    # Números do laudo validado (agregados, sem dados identificáveis)
    a = analisar_regime(35_203_688.26, -35_049_842.12, meses_observados=4.5)
    assert abs(a.volume_anualizado - 187_342_747.68) < 5_000, a.volume_anualizado
    assert abs(a.multiplo_do_teto - 39.0) < 0.5, a.multiplo_do_teto
    assert a.classe == "CRITICO"
    assert a.incompativel is True


def test_compativel_abaixo_do_teto():
    # R$ 2M/ano < teto R$ 4,8M
    a = analisar_regime(1_000_000, -1_000_000, meses_observados=12)
    assert a.multiplo_do_teto < 1.0
    assert a.classe == "COMPATIVEL"
    assert a.incompativel is False


def test_limiar_atencao_logo_acima_do_teto():
    # ~1,25× o teto → ATENCAO
    a = analisar_regime(3_000_000, -3_000_000, meses_observados=12)
    assert 1.0 < a.multiplo_do_teto <= 3.0
    assert a.classe == "ATENCAO"
    assert a.incompativel is True


def test_classe_alto_entre_3_e_10x():
    a = analisar_regime(12_000_000, -12_000_000, meses_observados=12)  # R$24M/ano = 5x
    assert a.classe == "ALTO"


def test_meses_zero_nao_divide_por_zero():
    a = analisar_regime(100, -100, meses_observados=0)
    assert a.volume_anualizado >= 0
    assert a.meses_observados == 1.0


def test_teto_mei():
    # MEI movimentando R$ 500k/ano = ~6,2× o teto MEI (R$ 81k)
    a = analisar_regime(250_000, -250_000, meses_observados=12, teto=TETO_MEI)
    assert a.multiplo_do_teto > 6
    assert a.classe in ("ALTO", "CRITICO")
    assert a.incompativel is True


def test_volume_bruto_soma_credito_e_debito_absolutos():
    a = analisar_regime(1_000_000, -500_000, meses_observados=12)
    assert a.volume_bruto == 1_500_000.0
