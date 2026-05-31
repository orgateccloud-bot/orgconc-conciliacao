"""Entidades de negocio. Imutaveis por default (frozen dataclasses)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class Severidade(str, Enum):
    CRITICO = "critico"
    ALERTA = "alerta"
    ATENCAO = "atencao"

    @property
    def ordem(self) -> int:
        return {"critico": 0, "alerta": 1, "atencao": 2}[self.value]


@dataclass(frozen=True, slots=True)
class Transacao:
    """Uma linha de extrato bancario."""
    conta: str
    data: date
    valor: Decimal
    memo: str = ""
    nome: str = ""
    tipo: str = ""           # OFX TRNTYPE (DEBIT/CREDIT/etc.)
    checknum: str | None = None
    categoria: str | None = None     # preenchido pelo ClassificadorContabil
    eh_anomalia: bool = False        # preenchido pelo DetectorAnomalias

    def chave_dedupe(self) -> tuple[str, date, Decimal, str]:
        """Chave para detectar duplicidade."""
        return (self.conta, self.data, self.valor.quantize(Decimal("0.01")), self.memo[:40])

    def texto_busca(self) -> str:
        return f"{self.memo} {self.nome}".upper()


@dataclass(frozen=True, slots=True)
class Extrato:
    """Conjunto de transacoes de UMA conta bancaria, de um upload."""
    arquivo: str
    conta: str
    transacoes: tuple[Transacao, ...] = ()

    @property
    def qtd(self) -> int:
        return len(self.transacoes)

    @property
    def total_credito(self) -> Decimal:
        return sum((t.valor for t in self.transacoes if t.valor > 0), Decimal("0"))

    @property
    def total_debito(self) -> Decimal:
        return sum((t.valor for t in self.transacoes if t.valor < 0), Decimal("0"))


@dataclass(frozen=True, slots=True)
class Anomalia:
    """Achado do DetectorAnomalias."""
    severidade: Severidade
    tipo: str          # "Duplicidade", "Valor alto", "Estorno", "Transferencia sem par"
    titulo: str
    conta: str
    valor: Decimal
    detalhe: str


@dataclass(frozen=True, slots=True)
class Cliente:
    """Cliente do escritorio contabil (organizacao usuaria do OrgConc)."""
    id: uuid.UUID
    nome: str
    cnpj: str | None = None
    email: str | None = None
    telefone: str | None = None
    plano: str = "basico"
    ativo: bool = True
    criado_em: datetime | None = None


@dataclass(frozen=True, slots=True)
class Conciliacao:
    """Resultado de um processamento de extratos."""
    id: uuid.UUID
    report_id: str
    modo: str                       # "llm" | "simulacao_local" | "multi_modelo" | ...
    total_transacoes: int
    total_anomalias: int
    cliente_id: uuid.UUID | None = None
    valor_total_credito: Decimal | None = None
    valor_total_debito: Decimal | None = None
    periodo_inicio: date | None = None
    periodo_fim: date | None = None
    criado_em: datetime | None = None
    relatorio_md: str = ""
    extratos: tuple[Extrato, ...] = field(default_factory=tuple)
    anomalias: tuple[Anomalia, ...] = field(default_factory=tuple)
