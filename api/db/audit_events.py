"""Consultas de audit_events."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditEvent


async def listar_eventos(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    actor_email: Optional[str] = None,
    resource_type: Optional[str] = None,
) -> list[AuditEvent]:
    q = select(AuditEvent).order_by(AuditEvent.ts.desc()).limit(limit).offset(offset)
    if actor_email:
        q = q.where(AuditEvent.actor_email == actor_email)
    if resource_type:
        q = q.where(AuditEvent.resource_type == resource_type)
    result = await db.execute(q)
    return list(result.scalars().all())


async def contar_eventos(db: AsyncSession) -> int:
    from sqlalchemy import func
    q = select(func.count(AuditEvent.id))
    result = await db.execute(q)
    return int(result.scalar_one() or 0)
