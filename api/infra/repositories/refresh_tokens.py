"""Wrapper class-based em torno de api/db/refresh_tokens.py (funcoes existentes).

Permite injetar a interface RefreshTokenRepository nos use cases — sem reescrever
o CRUD ja testado em produção.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from api.db import refresh_tokens as _legacy


class RefreshTokenRepositorySQL:
    def __init__(self, session: AsyncSession):
        self._db = session

    async def criar(
        self,
        *,
        sub: str,
        token_hash: str,
        expira_em: datetime,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> uuid.UUID:
        rt = await _legacy.criar(
            self._db,
            sub=sub,
            token_hash=token_hash,
            expira_em=expira_em,
            ip=ip,
            user_agent=user_agent,
        )
        return rt.id

    async def buscar_ativo_por_hash(self, token_hash: str):
        return await _legacy.buscar_ativo_por_hash(self._db, token_hash)

    async def revogar(self, rt_id: uuid.UUID, substituido_por: uuid.UUID | None = None) -> None:
        await _legacy.revogar(self._db, rt_id, substituido_por=substituido_por)

    async def revogar_por_hash(self, token_hash: str) -> bool:
        return await _legacy.revogar_por_hash(self._db, token_hash)

    async def revogar_todos_do_sub(self, sub: str) -> int:
        return await _legacy.revogar_todos_do_sub(self._db, sub)
