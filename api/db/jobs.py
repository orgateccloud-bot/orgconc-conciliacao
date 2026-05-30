"""CRUD de jobs assincronos."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Job


async def criar(
    db: AsyncSession,
    *,
    sub: str,
    tipo: str,
    input_data: dict[str, Any] | None = None,
) -> Job:
    j = Job(
        sub=sub,
        tipo=tipo,
        status="queued",
        input_json=json.dumps(input_data) if input_data else None,
    )
    db.add(j)
    await db.commit()
    await db.refresh(j)
    return j


async def buscar(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    return await db.get(Job, job_id)


async def listar_do_sub(db: AsyncSession, sub: str, limit: int = 50) -> list[Job]:
    q = (
        select(Job)
        .where(Job.sub == sub)
        .order_by(Job.criado_em.desc())
        .limit(min(limit, 100))
    )
    result = await db.execute(q)
    return list(result.scalars().all())


async def marcar_running(db: AsyncSession, job_id: uuid.UUID) -> None:
    agora = datetime.now(timezone.utc)
    await db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="running", iniciado_em=agora)
    )
    await db.commit()


async def atualizar_progresso(db: AsyncSession, job_id: uuid.UUID, progresso: int) -> None:
    await db.execute(
        update(Job).where(Job.id == job_id).values(progresso=max(0, min(100, progresso)))
    )
    await db.commit()


async def marcar_done(db: AsyncSession, job_id: uuid.UUID, output_data: dict[str, Any]) -> None:
    agora = datetime.now(timezone.utc)
    await db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status="done",
            output_json=json.dumps(output_data, default=str),
            progresso=100,
            finalizado_em=agora,
        )
    )
    await db.commit()


async def marcar_failed(db: AsyncSession, job_id: uuid.UUID, erro: str) -> None:
    agora = datetime.now(timezone.utc)
    await db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="failed", erro=erro[:2000], finalizado_em=agora)
    )
    await db.commit()


async def marcar_cancelled(db: AsyncSession, job_id: uuid.UUID) -> None:
    agora = datetime.now(timezone.utc)
    await db.execute(
        update(Job)
        .where(Job.id == job_id)
        .where(Job.status.in_(("queued", "running")))
        .values(status="cancelled", finalizado_em=agora)
    )
    await db.commit()
