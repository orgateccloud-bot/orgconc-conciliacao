"""CRUD de usuários (login multi-org).

Convenção: o email é normalizado para lowercase aqui (criação e busca), para
casar com o índice unique e evitar usuários duplicados por diferença de caixa.
Nunca recebemos a senha em claro — apenas o `senha_hash` (bcrypt via
api.services.auth.hash_senha).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Usuario


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


async def criar(
    db: AsyncSession,
    *,
    email: str,
    senha_hash: str,
    org_id: str | uuid.UUID,
    role: str = "user",
    nome: str | None = None,
) -> Usuario:
    u = Usuario(
        email=_norm_email(email),
        senha_hash=senha_hash,
        org_id=org_id,
        role=role,
        nome=nome,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def buscar_por_email(db: AsyncSession, email: str) -> Usuario | None:
    """Usuário ATIVO com este email (case-insensitive), ou None."""
    q = (
        select(Usuario)
        .where(Usuario.email == _norm_email(email))
        .where(Usuario.ativo.is_(True))
    )
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def buscar_por_id(db: AsyncSession, usuario_id: str | uuid.UUID) -> Usuario | None:
    """Usuário ATIVO por id (usado pelo refresh para re-derivar org/role), ou None.

    Aceita id em str (vem do claim `sub` do JWT); id inválido → None.
    """
    try:
        uid = usuario_id if isinstance(usuario_id, uuid.UUID) else uuid.UUID(str(usuario_id))
    except (ValueError, AttributeError, TypeError):
        return None
    q = select(Usuario).where(Usuario.id == uid).where(Usuario.ativo.is_(True))
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def registrar_login(db: AsyncSession, usuario_id: str | uuid.UUID) -> None:
    """Carimba ultimo_login_em = agora."""
    stmt = (
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(ultimo_login_em=datetime.now(timezone.utc))
    )
    await db.execute(stmt)
    await db.commit()


async def atualizar_senha(db: AsyncSession, usuario_id: str | uuid.UUID, senha_hash: str) -> int:
    """Define um novo senha_hash. Retorna nº de linhas afetadas (0 se id inexistente)."""
    stmt = (
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(senha_hash=senha_hash, atualizado_em=datetime.now(timezone.utc))
    )
    res = await db.execute(stmt)
    await db.commit()
    return res.rowcount or 0


async def listar_por_org(db: AsyncSession, org_id: str | uuid.UUID) -> list[Usuario]:
    q = select(Usuario).where(Usuario.org_id == org_id).order_by(Usuario.criado_em)
    result = await db.execute(q)
    return list(result.scalars().all())
