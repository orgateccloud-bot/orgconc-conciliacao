"""Consultas de conciliacoes persistidas."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Conciliacao


async def listar_conciliacoes(
    db: AsyncSession,
    *,
    cliente_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Conciliacao]:
    q = select(Conciliacao).order_by(Conciliacao.criado_em.desc()).limit(limit).offset(offset)
    if cliente_id:
        q = q.where(Conciliacao.cliente_id == cliente_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def buscar_por_report_id(db: AsyncSession, report_id: str) -> Conciliacao | None:
    result = await db.execute(select(Conciliacao).where(Conciliacao.report_id == report_id))
    return result.scalar_one_or_none()
