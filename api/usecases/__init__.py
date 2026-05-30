"""Camada de aplicacao — use cases (1 caso de uso = 1 classe).

Cada use case:
- Recebe um Input dataclass tipado
- Orquestra entidades de dominio + adapters de infra (via interfaces/Protocols)
- Retorna um Output dataclass tipado
- Levanta DomainError em vez de HTTPException (router converte)
"""
from api.usecases.criar_cliente import (
    CriarClienteInput,
    CriarClienteOutput,
    CriarClienteUseCase,
)
from api.usecases.listar_clientes import (
    ListarClientesInput,
    ListarClientesUseCase,
)
from api.usecases.listar_conciliacoes import (
    ListarConciliacoesInput,
    ListarConciliacoesUseCase,
)

__all__ = [
    "CriarClienteInput",
    "CriarClienteOutput",
    "CriarClienteUseCase",
    "ListarClientesInput",
    "ListarClientesUseCase",
    "ListarConciliacoesInput",
    "ListarConciliacoesUseCase",
]
