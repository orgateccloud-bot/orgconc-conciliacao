"""CRUD de refresh tokens.

Convencao: nunca recebemos o token plain — apenas o hash sha256(token).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import RefreshToken


async def criar(
    db: AsyncSession,
    *,
    sub: str,
    token_hash: str,
    expira_em: datetime,
    role: str = "user",
    cliente_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> RefreshToken:
    rt = RefreshToken(
        sub=sub,
        role=role,
        cliente_id=cliente_id,
        token_hash=token_hash,
        expira_em=expira_em,
        ip=ip,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(rt)
    await db.commit()
    await db.refresh(rt)
    return rt


async def buscar_ativo_por_hash(db: AsyncSession, token_hash: str) -> RefreshToken | None:
    """Retorna o token se: existe, nao revogado, nao expirado."""
    agora = datetime.now(timezone.utc)
    q = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .where(RefreshToken.revogado_em.is_(None))
        .where(RefreshToken.expira_em > agora)
    )
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def revogar(
    db: AsyncSession,
    rt_id: uuid.UUID,
    substituido_por: uuid.UUID | None = None,
) -> None:
    agora = datetime.now(timezone.utc)
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.id == rt_id)
        .where(RefreshToken.revogado_em.is_(None))
        .values(revogado_em=agora, substituido_por=substituido_por)
    )
    await db.execute(stmt)
    await db.commit()


async def revogar_por_hash(db: AsyncSession, token_hash: str) -> bool:
    """True se algum token foi revogado."""
    agora = datetime.now(timezone.utc)
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .where(RefreshToken.revogado_em.is_(None))
        .values(revogado_em=agora)
    )
    result = await db.execute(stmt)
    await db.commit()
    return (result.rowcount or 0) > 0


async def revogar_todos_do_sub(db: AsyncSession, sub: str) -> int:
    """Logout global — revoga todos os refresh tokens ativos do usuario."""
    agora = datetime.now(timezone.utc)
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.sub == sub)
        .where(RefreshToken.revogado_em.is_(None))
        .values(revogado_em=agora)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
