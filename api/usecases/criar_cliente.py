"""Use case: criar cliente."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from api.domain.entities import Cliente
from api.domain.exceptions import RegraViolada
from api.domain.repositories import ClienteRepository
from api.domain.value_objects import CNPJ


@dataclass(frozen=True)
class CriarClienteInput:
    nome: str
    cnpj: str | None = None
    email: str | None = None
    telefone: str | None = None
    plano: str = "basico"


@dataclass(frozen=True)
class CriarClienteOutput:
    cliente: Cliente


class CriarClienteUseCase:
    PLANOS_VALIDOS = {"basico", "pro", "enterprise"}

    def __init__(self, repo: ClienteRepository):
        self._repo = repo

    async def execute(self, input: CriarClienteInput) -> CriarClienteOutput:
        if input.plano not in self.PLANOS_VALIDOS:
            raise RegraViolada(f"Plano invalido: {input.plano}")

        cnpj_normalizado: str | None = None
        if input.cnpj:
            cnpj_normalizado = CNPJ(input.cnpj).digitos  # valida DV
            existente = await self._repo.buscar_por_cnpj(cnpj_normalizado)
            if existente is not None:
                raise RegraViolada("CNPJ ja cadastrado")

        novo = Cliente(
            id=uuid.uuid4(),
            nome=input.nome.strip(),
            cnpj=cnpj_normalizado,
            email=(input.email or "").strip() or None,
            telefone=(input.telefone or "").strip() or None,
            plano=input.plano,
        )
        criado = await self._repo.criar(novo)
        return CriarClienteOutput(cliente=criado)
