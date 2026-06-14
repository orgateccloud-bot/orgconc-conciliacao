"""CRUD de refresh tokens.

Convencao: nunca recebemos o token plain — apenas o hash sha256(token).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import RefreshToken

# #25 — limite de sessoes (refresh tokens ativos) simultaneas por `sub`. Ao
# exceder, revoga as mais antigas. Configuravel por env; <= 0 desativa o limite.
MAX_SESSOES_POR_SUB = int(os.environ.get("ORGCONC_MAX_SESSOES", "10"))


async def _revogar_excedentes_do_sub(db: AsyncSession, sub: str, manter: int) -> int:
    """Revoga as sessoes ativas mais ANTIGAS do `sub` ate sobrarem `manter` (#25).

    Conta os refresh tokens ativos (nao revogados, nao expirados) do sub; se
    forem > `manter`, revoga os excedentes mais antigos (ordem por emitido_em).
    NAO commita — roda dentro da transacao de quem chama `criar`. Retorna o
    numero de tokens revogados.
    """
    if manter < 0:
        return 0
    agora = datetime.now(timezone.utc)
    ativos_q = (
        select(RefreshToken.id)
        .where(RefreshToken.sub == sub)
        .where(RefreshToken.revogado_em.is_(None))
        .where(RefreshToken.expira_em > agora)
        .order_by(RefreshToken.emitido_em.asc())
    )
    ids = (await db.execute(ativos_q)).scalars().all()
    excedentes = ids[: max(0, len(ids) - manter)]
    if not excedentes:
        return 0
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.id.in_(excedentes))
        .where(RefreshToken.revogado_em.is_(None))
        .values(revogado_em=agora)
    )
    res = await db.execute(stmt)
    return res.rowcount or 0


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
    commit: bool = True,
) -> RefreshToken:
    """Cria (persiste) um refresh token.

    `commit=False` deixa a transacao aberta — usado pela rotacao atomica (#22),
    que cria o novo e revoga o antigo num unico commit. Nesse caso quem chama
    e responsavel por commitar.
    """
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
    # #25 — flush() materializa o INSERT para que a nova sessao seja contada e
    # ordenada junto com as existentes; depois revogamos as mais antigas ate
    # sobrarem MAX (a nova, por ser a mais recente, fica entre as mantidas).
    # Total ativo apos o commit: <= MAX.
    if MAX_SESSOES_POR_SUB > 0:
        await db.flush()
        await _revogar_excedentes_do_sub(db, sub, manter=MAX_SESSOES_POR_SUB)
    if commit:
        await db.commit()
        await db.refresh(rt)
    else:
        await db.flush()
        await db.refresh(rt)  # popula rt.id sem fechar a transacao
    return rt


async def buscar_ativo_por_hash(
    db: AsyncSession, token_hash: str, *, for_update: bool = False
) -> RefreshToken | None:
    """Retorna o token se: existe, nao revogado, nao expirado.

    #22 — `for_update=True` aplica `SELECT ... FOR UPDATE` (lock de linha) para
    serializar a rotacao concorrente: dois /auth/refresh simultaneos com o mesmo
    refresh disputam o lock; o primeiro consome (revoga) o token, e o segundo,
    ao readquirir o lock, ja nao casa o filtro `revogado_em IS NULL` -> recebe
    None -> a reuse-detection (401) dispara. Sem o lock, ambos veriam o token
    ativo e emitiriam dois novos validos (~janela de corrida). Exige rodar
    dentro de uma transacao (o `async with SessionLocal()` ja abre uma)."""
    agora = datetime.now(timezone.utc)
    q = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .where(RefreshToken.revogado_em.is_(None))
        .where(RefreshToken.expira_em > agora)
    )
    if for_update:
        q = q.with_for_update()
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def revogar(
    db: AsyncSession,
    rt_id: uuid.UUID,
    substituido_por: uuid.UUID | None = None,
    *,
    commit: bool = True,
) -> None:
    """Revoga um refresh token por id.

    `commit=False` mantem a transacao aberta (rotacao atomica #22 — criar novo +
    revogar antigo num unico commit). Quem chama commita.
    """
    agora = datetime.now(timezone.utc)
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.id == rt_id)
        .where(RefreshToken.revogado_em.is_(None))
        .values(revogado_em=agora, substituido_por=substituido_por)
    )
    await db.execute(stmt)
    if commit:
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
