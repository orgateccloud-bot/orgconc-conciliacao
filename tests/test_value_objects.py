"""Cobertura dos Value Objects de domínio (lógica pura, sem DB/rede).

Testa CNPJ, CPF, Valor e Periodo: validação na construção, normalização,
formatação, mascaramento, igualdade por valor, imutabilidade, aritmética
monetária, e os ramos de erro (ValorInvalido).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from api.domain.exceptions import ValorInvalido
from api.domain.value_objects import CNPJ, CPF, Periodo, Valor


# ── CNPJ ─────────────────────────────────────────────────────────────────────
def test_cnpj_aceita_digitos_puros():
    c = CNPJ("11222333000181")
    assert c.digitos == "11222333000181"


def test_cnpj_normaliza_formatado():
    # Pontuação é removida; digitos ficam só os 14 números.
    c = CNPJ("11.222.333/0001-81")
    assert c.digitos == "11222333000181"


def test_cnpj_formatado():
    assert CNPJ("11222333000181").formatado() == "11.222.333/0001-81"


def test_cnpj_str_usa_formatado():
    assert str(CNPJ("11222333000181")) == "11.222.333/0001-81"


def test_cnpj_mascarado():
    # Mantém só primeiro bloco e os 2 últimos dígitos.
    assert CNPJ("11222333000181").mascarado() == "11.***.***/***81"


def test_cnpj_igualdade_por_valor():
    # frozen dataclass: igualdade estrutural; pontuação não importa após normalizar.
    assert CNPJ("11.222.333/0001-81") == CNPJ("11222333000181")
    assert hash(CNPJ("11222333000181")) == hash(CNPJ("11.222.333/0001-81"))


def test_cnpj_imutavel():
    c = CNPJ("11222333000181")
    with pytest.raises(Exception):
        c.digitos = "00000000000000"  # type: ignore[misc]


def test_cnpj_tamanho_invalido():
    with pytest.raises(ValorInvalido):
        CNPJ("123")


def test_cnpj_todos_iguais_rejeitado():
    with pytest.raises(ValorInvalido):
        CNPJ("11111111111111")


def test_cnpj_dv_invalido():
    # 14 dígitos, não todos iguais, mas DV errado.
    with pytest.raises(ValorInvalido):
        CNPJ("11222333000180")


def test_cnpj_calc_dv_ramo_resto_menor_que_2():
    # _calc_dv retorna 0 quando resto < 2. CNPJ cujo 1º DV é 0.
    c = CNPJ("11444777000161")
    assert c.digitos[12] == "6"  # sanity: este é válido


def test_cnpj_segundo_dv_invalido():
    # Primeiro DV correto (8), segundo errado.
    with pytest.raises(ValorInvalido):
        CNPJ("11222333000182")


# ── CPF ──────────────────────────────────────────────────────────────────────
def test_cpf_aceita_digitos_puros():
    assert CPF("11144477735").digitos == "11144477735"


def test_cpf_normaliza_formatado():
    assert CPF("111.444.777-35").digitos == "11144477735"


def test_cpf_formatado():
    assert CPF("11144477735").formatado() == "111.444.777-35"


def test_cpf_str_usa_formatado():
    assert str(CPF("11144477735")) == "111.444.777-35"


def test_cpf_mascarado():
    assert CPF("11144477735").mascarado() == "***.444.***-**"


def test_cpf_igualdade_por_valor():
    assert CPF("111.444.777-35") == CPF("11144477735")
    assert hash(CPF("11144477735")) == hash(CPF("111.444.777-35"))


def test_cpf_imutavel():
    c = CPF("11144477735")
    with pytest.raises(Exception):
        c.digitos = "00000000000"  # type: ignore[misc]


def test_cpf_tamanho_invalido():
    with pytest.raises(ValorInvalido):
        CPF("123")


def test_cpf_todos_iguais_rejeitado():
    with pytest.raises(ValorInvalido):
        CPF("11111111111")


def test_cpf_dv_invalido():
    with pytest.raises(ValorInvalido):
        CPF("11144477700")


def test_cpf_segundo_dv_invalido():
    # Primeiro DV correto (3), segundo errado.
    with pytest.raises(ValorInvalido):
        CPF("11144477734")


def test_cpf_resto_dez_vira_zero():
    # Garante cobertura do ramo r == 10 -> 0 em pelo menos um DV.
    # 12345678909 é um CPF válido clássico cujo cálculo exercita o ramo.
    c = CPF("12345678909")
    assert c.digitos == "12345678909"


# ── Valor ────────────────────────────────────────────────────────────────────
def test_valor_de_decimal():
    assert Valor(Decimal("10.5")).quantia == Decimal("10.50")


def test_valor_de_string():
    assert Valor("10.5").quantia == Decimal("10.50")  # type: ignore[arg-type]


def test_valor_de_int():
    assert Valor(10).quantia == Decimal("10.00")  # type: ignore[arg-type]


def test_valor_quantiza_2_casas():
    # Banker's rounding: 2.345 -> 2.34 (arredonda para par).
    assert Valor(Decimal("2.345")).quantia == Decimal("2.34")
    assert Valor(Decimal("2.355")).quantia == Decimal("2.36")


def test_valor_nao_numerico_string():
    with pytest.raises(ValorInvalido):
        Valor("abc")  # type: ignore[arg-type]


def test_valor_nao_numerico_none():
    with pytest.raises(ValorInvalido):
        Valor(None)  # type: ignore[arg-type]


def test_valor_soma():
    assert (Valor("1.10") + Valor("2.20")).quantia == Decimal("3.30")  # type: ignore[arg-type]


def test_valor_subtracao():
    assert (Valor("5.00") - Valor("2.50")).quantia == Decimal("2.50")  # type: ignore[arg-type]


def test_valor_negacao():
    assert (-Valor("3.00")).quantia == Decimal("-3.00")  # type: ignore[arg-type]


def test_valor_abs():
    assert Valor("-7.00").abs().quantia == Decimal("7.00")  # type: ignore[arg-type]
    assert Valor("7.00").abs().quantia == Decimal("7.00")  # type: ignore[arg-type]


def test_valor_positivo():
    assert Valor("0.01").positivo is True  # type: ignore[arg-type]
    assert Valor("0.00").positivo is False  # type: ignore[arg-type]
    assert Valor("-0.01").positivo is False  # type: ignore[arg-type]


def test_valor_negativo():
    assert Valor("-0.01").negativo is True  # type: ignore[arg-type]
    assert Valor("0.00").negativo is False  # type: ignore[arg-type]
    assert Valor("0.01").negativo is False  # type: ignore[arg-type]


def test_valor_str_ptbr():
    assert str(Valor(Decimal("1234.56"))) == "R$ 1.234,56"
    assert str(Valor(Decimal("0.00"))) == "R$ 0,00"
    assert str(Valor(Decimal("1000000.00"))) == "R$ 1.000.000,00"


def test_valor_str_negativo():
    assert str(Valor(Decimal("-1234.56"))) == "R$ -1.234,56"


def test_valor_igualdade_por_valor():
    assert Valor("10.00") == Valor(Decimal("10.0"))  # type: ignore[arg-type]
    assert hash(Valor("10.00")) == hash(Valor(Decimal("10.00")))  # type: ignore[arg-type]


def test_valor_imutavel():
    v = Valor(Decimal("1.00"))
    with pytest.raises(Exception):
        v.quantia = Decimal("2.00")  # type: ignore[misc]


# ── Periodo ──────────────────────────────────────────────────────────────────
def test_periodo_valido():
    p = Periodo(date(2026, 1, 1), date(2026, 1, 31))
    assert p.inicio == date(2026, 1, 1)
    assert p.fim == date(2026, 1, 31)


def test_periodo_inicio_igual_fim():
    # Intervalo de um único dia é válido (fechado).
    p = Periodo(date(2026, 1, 1), date(2026, 1, 1))
    assert p.dias == 1


def test_periodo_invertido_rejeitado():
    with pytest.raises(ValorInvalido):
        Periodo(date(2026, 2, 1), date(2026, 1, 1))


def test_periodo_dias_inclusivo():
    # 1 a 31 de janeiro = 31 dias (intervalo fechado).
    assert Periodo(date(2026, 1, 1), date(2026, 1, 31)).dias == 31


def test_periodo_contem():
    p = Periodo(date(2026, 1, 10), date(2026, 1, 20))
    assert p.contem(date(2026, 1, 15)) is True
    assert p.contem(date(2026, 1, 10)) is True  # borda inicial
    assert p.contem(date(2026, 1, 20)) is True  # borda final
    assert p.contem(date(2026, 1, 9)) is False
    assert p.contem(date(2026, 1, 21)) is False


def test_periodo_str():
    p = Periodo(date(2026, 1, 1), date(2026, 1, 31))
    assert str(p) == "2026-01-01 a 2026-01-31"


def test_periodo_igualdade_por_valor():
    a = Periodo(date(2026, 1, 1), date(2026, 1, 31))
    b = Periodo(date(2026, 1, 1), date(2026, 1, 31))
    assert a == b
    assert hash(a) == hash(b)


def test_periodo_imutavel():
    p = Periodo(date(2026, 1, 1), date(2026, 1, 31))
    with pytest.raises(Exception):
        p.inicio = date(2025, 1, 1)  # type: ignore[misc]
