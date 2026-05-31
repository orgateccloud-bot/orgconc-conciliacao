"""Camada de dominio do OrgConc.

REGRA DE OURO: este pacote NAO importa nada externo
(sem FastAPI, sem SQLAlchemy, sem anthropic, sem requests).
So Python stdlib + pydantic (opcional, para validacao).

Subpacotes:
- entities      : entidades de negocio (Transacao, Extrato, Anomalia, Conciliacao, Cliente)
- value_objects : objetos imutaveis com validacao (CNPJ, CPF, Valor, Periodo)
- services      : regras de negocio puras (ClassificadorContabil, DetectorAnomalias)
- repositories  : Protocols (interfaces) implementadas pela camada infra
- exceptions    : erros de dominio
"""

from api.domain.entities import (
    Anomalia,
    Cliente,
    Conciliacao,
    Extrato,
    Severidade,
    Transacao,
)
from api.domain.exceptions import (
    DomainError,
    RegraViolada,
    ValorInvalido,
)
from api.domain.value_objects import (
    CNPJ,
    CPF,
    Periodo,
    Valor,
)

__all__ = [
    "Anomalia",
    "Cliente",
    "Conciliacao",
    "Extrato",
    "Severidade",
    "Transacao",
    "DomainError",
    "RegraViolada",
    "ValorInvalido",
    "CNPJ",
    "CPF",
    "Periodo",
    "Valor",
]
