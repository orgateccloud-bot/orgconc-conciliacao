"""Use case: listar clientes."""
from __future__ import annotations

from dataclasses import dataclass

from api.domain.entities import Cliente
from api.domain.repositories import ClienteRepository


@dataclass(frozen=True)
class ListarClientesInput:
    apenas_ativos: bool = True


class ListarClientesUseCase:
    def __init__(self, repo: ClienteRepository):
        self._repo = repo

    async def execute(self, input: ListarClientesInput) -> list[Cliente]:
        return await self._repo.listar(apenas_ativos=input.apenas_ativos)
