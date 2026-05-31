"""Implementacao SQLAlchemy do ClienteRepository."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Cliente as ClienteOrm
from api.domain.entities import Cliente


def _to_entity(row: ClienteOrm) -> Cliente:
    return Cliente(
        id=row.id,
        nome=row.nome,
        cnpj=row.cnpj,
        email=row.email,
        telefone=row.telefone,
        plano=row.plano,
        ativo=row.ativo,
        criado_em=row.criado_em,
    )


_CAMPOS_EDITAVEIS = {"nome", "email", "telefone", "plano", "ativo"}


class ClienteRepositorySQL:
    """Concretizacao SQLAlchemy da interface ClienteRepository."""

    def __init__(self, session: AsyncSession):
        self._db = session

    async def criar(self, cliente: Cliente) -> Cliente:
        orm = ClienteOrm(
            nome=cliente.nome,
            cnpj=cliente.cnpj,
            email=cliente.email,
            telefone=cliente.telefone,
            plano=cliente.plano,
        )
        self._db.add(orm)
        await self._db.commit()
        await self._db.refresh(orm)
        return _to_entity(orm)

    async def buscar_por_id(self, cliente_id: uuid.UUID) -> Cliente | None:
        row = await self._db.get(ClienteOrm, cliente_id)
        return _to_entity(row) if row else None

    async def buscar_por_cnpj(self, cnpj: str) -> Cliente | None:
        result = await self._db.execute(select(ClienteOrm).where(ClienteOrm.cnpj == cnpj))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def listar(self, *, apenas_ativos: bool = True) -> list[Cliente]:
        q = select(ClienteOrm)
        if apenas_ativos:
            q = q.where(ClienteOrm.ativo.is_(True))
        q = q.order_by(ClienteOrm.nome)
        result = await self._db.execute(q)
        return [_to_entity(r) for r in result.scalars().all()]

    async def atualizar(self, cliente_id: uuid.UUID, **campos: object) -> Cliente | None:
        validos = {k: v for k, v in campos.items() if k in _CAMPOS_EDITAVEIS}
        row = await self._db.get(ClienteOrm, cliente_id)
        if not row:
            return None
        for k, v in validos.items():
            setattr(row, k, v)
        await self._db.commit()
        await self._db.refresh(row)
        return _to_entity(row)
