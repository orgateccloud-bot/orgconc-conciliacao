"""Value Objects — imutaveis, validados na construcao, comparados por valor."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import ClassVar

from api.domain.exceptions import ValorInvalido


# ── CNPJ ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CNPJ:
    """CNPJ brasileiro (14 digitos). Validacao DV inclusa."""
    digitos: str

    _RE_NAO_DIGITO: ClassVar[re.Pattern[str]] = re.compile(r"\D")
    _P1: ClassVar[list[int]] = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    _P2: ClassVar[list[int]] = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def __post_init__(self) -> None:
        d = self._RE_NAO_DIGITO.sub("", self.digitos)
        if len(d) != 14 or len(set(d)) == 1:
            raise ValorInvalido(f"CNPJ invalido (tamanho ou todos iguais): {self.digitos}")
        if not self._validar_dv(d):
            raise ValorInvalido(f"CNPJ invalido (digitos verificadores): {self.digitos}")
        object.__setattr__(self, "digitos", d)

    @classmethod
    def _calc_dv(cls, d: str, pesos: list[int]) -> int:
        s = sum(int(d[i]) * pesos[i] for i in range(len(pesos)))
        r = s % 11
        return 0 if r < 2 else 11 - r

    @classmethod
    def _validar_dv(cls, d: str) -> bool:
        return int(d[12]) == cls._calc_dv(d, cls._P1) and int(d[13]) == cls._calc_dv(d, cls._P2)

    def formatado(self) -> str:
        d = self.digitos
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"

    def mascarado(self) -> str:
        """Para logs: mantem so primeiro e ultimo bloco."""
        d = self.digitos
        return f"{d[:2]}.***.***/***{d[-2:]}"

    def __str__(self) -> str:
        return self.formatado()


# ── CPF ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CPF:
    """CPF brasileiro (11 digitos)."""
    digitos: str

    _RE_NAO_DIGITO: ClassVar[re.Pattern[str]] = re.compile(r"\D")

    def __post_init__(self) -> None:
        d = self._RE_NAO_DIGITO.sub("", self.digitos)
        if len(d) != 11 or len(set(d)) == 1:
            raise ValorInvalido(f"CPF invalido: {self.digitos}")
        if not self._validar_dv(d):
            raise ValorInvalido(f"CPF invalido (DV): {self.digitos}")
        object.__setattr__(self, "digitos", d)

    @staticmethod
    def _validar_dv(d: str) -> bool:
        def calc(parcial: str, peso_inicial: int) -> int:
            s = sum(int(parcial[i]) * (peso_inicial - i) for i in range(len(parcial)))
            r = (s * 10) % 11
            return 0 if r == 10 else r
        return int(d[9]) == calc(d[:9], 10) and int(d[10]) == calc(d[:10], 11)

    def formatado(self) -> str:
        d = self.digitos
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"

    def mascarado(self) -> str:
        d = self.digitos
        return f"***.{d[3:6]}.***-**"

    def __str__(self) -> str:
        return self.formatado()


# ── Valor (Decimal monetario) ──────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Valor:
    """Valor monetario com 2 casas decimais, sempre Decimal."""
    quantia: Decimal

    def __post_init__(self) -> None:
        try:
            q = Decimal(self.quantia) if not isinstance(self.quantia, Decimal) else self.quantia
        except (InvalidOperation, TypeError) as e:
            raise ValorInvalido(f"Valor nao numerico: {self.quantia!r}") from e
        # Normaliza para 2 casas (banker's rounding e padrao em DecimalContext)
        object.__setattr__(self, "quantia", q.quantize(Decimal("0.01")))

    def __add__(self, outro: "Valor") -> "Valor":
        return Valor(self.quantia + outro.quantia)

    def __sub__(self, outro: "Valor") -> "Valor":
        return Valor(self.quantia - outro.quantia)

    def __neg__(self) -> "Valor":
        return Valor(-self.quantia)

    def abs(self) -> "Valor":
        return Valor(abs(self.quantia))

    @property
    def positivo(self) -> bool:
        return self.quantia > 0

    @property
    def negativo(self) -> bool:
        return self.quantia < 0

    def __str__(self) -> str:
        # pt-BR: R$ 1.234,56
        s = f"{self.quantia:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"


# ── Periodo ────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Periodo:
    """Intervalo fechado de datas [inicio, fim]."""
    inicio: date
    fim: date

    def __post_init__(self) -> None:
        if self.inicio > self.fim:
            raise ValorInvalido(f"Periodo invalido: inicio {self.inicio} > fim {self.fim}")

    @property
    def dias(self) -> int:
        return (self.fim - self.inicio).days + 1

    def contem(self, d: date) -> bool:
        return self.inicio <= d <= self.fim

    def __str__(self) -> str:
        return f"{self.inicio.isoformat()} a {self.fim.isoformat()}"
