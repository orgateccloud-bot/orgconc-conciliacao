"""Use case: listar conciliacoes (com filtro opcional por cliente)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from api.domain.entities import Conciliacao
from api.domain.repositories import ConciliacaoRepository


@dataclass(frozen=True)
class ListarConciliacoesInput:
    cliente_id: uuid.UUID | None = None
    limit: int = 50
    offset: int = 0


class ListarConciliacoesUseCase:
    def __init__(self, repo: ConciliacaoRepository):
        self._repo = repo

    async def execute(self, input: ListarConciliacoesInput) -> list[Conciliacao]:
        return await self._repo.listar(
            cliente_id=input.cliente_id,
            limit=input.limit,
            offset=input.offset,
        )
