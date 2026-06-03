"""Contexto de RLS por organização (tenant = org_id).

Liga o usuário autenticado à sessão de banco: guarda o org_id do request num
ContextVar (isolado por task no event loop) e o aplica via `SET LOCAL app.org_id`
no início da transação, para a policy `org_isolation` (db/rls/org_isolation.sql)
filtrar as linhas no banco.

PREPARADO, NÃO ATIVO: enquanto o backend conectar como `postgres` (BYPASSRLS) e o
token não trouxer org_id, `set_org_context` recebe None e `aplicar_rls` é no-op —
o comportamento atual é preservado. Ver db/rls/README.md (rollout).
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# org_id (uuid em str) do request atual. None = sem tenant (estado atual).
_org_atual: ContextVar[Optional[str]] = ContextVar("orgconc_org_id", default=None)


def set_org_context(org_id: Optional[str]) -> None:
    """Define o org_id do request atual (a partir do token autenticado)."""
    _org_atual.set(str(org_id) if org_id else None)


def get_org_context() -> Optional[str]:
    """org_id do request atual, ou None se sem tenant."""
    return _org_atual.get()


async def aplicar_rls(session: AsyncSession) -> None:
    """Aplica `SET LOCAL app.org_id` na sessão a partir do contexto.

    No-op se não houver org no contexto (preserva o comportamento atual). Usa
    `set_config(..., is_local=true)`: o valor vale apenas dentro da transação
    corrente — para múltiplas transações por request, prefira um listener
    `after_begin` no rollout (ver db/rls/README.md). Idempotente.
    """
    org = _org_atual.get()
    if not org:
        return
    await session.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": org})
