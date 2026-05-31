"""Interfaces (Protocols) que a camada infra implementa.

Use cases dependem destas abstracoes — nao das implementacoes concretas.
Isso permite mockar trivialmente em testes (`InMemoryClienteRepository`).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from api.domain.entities import Cliente, Conciliacao


@runtime_checkable
class ClienteRepository(Protocol):
    async def criar(self, cliente: Cliente) -> Cliente: ...
    async def buscar_por_id(self, cliente_id: uuid.UUID) -> Cliente | None: ...
    async def buscar_por_cnpj(self, cnpj: str) -> Cliente | None: ...
    async def listar(self, *, apenas_ativos: bool = True) -> list[Cliente]: ...
    async def atualizar(self, cliente_id: uuid.UUID, **campos: object) -> Cliente | None: ...


@runtime_checkable
class ConciliacaoRepository(Protocol):
    async def salvar(self, conciliacao: Conciliacao) -> Conciliacao: ...
    async def listar(
        self,
        *,
        cliente_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conciliacao]: ...
    async def buscar_por_report_id(self, report_id: str) -> Conciliacao | None: ...


@runtime_checkable
class RefreshTokenRepository(Protocol):
    async def criar(
        self,
        *,
        sub: str,
        token_hash: str,
        expira_em: datetime,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> uuid.UUID: ...

    async def buscar_ativo_por_hash(self, token_hash: str) -> object | None: ...

    async def revogar(
        self,
        rt_id: uuid.UUID,
        substituido_por: uuid.UUID | None = None,
    ) -> None: ...

    async def revogar_por_hash(self, token_hash: str) -> bool: ...

    async def revogar_todos_do_sub(self, sub: str) -> int: ...
