"""Contexto de RLS por organização (tenant = org_id).

Liga o usuário autenticado à sessão de banco: guarda o org_id do request num
ContextVar (isolado por task no event loop) e o aplica via `SET LOCAL app.org_id`
no início de CADA transação (listener `after_begin`), para a policy
`org_isolation` (db/rls/org_isolation.sql) filtrar as linhas no banco.

O contextvar é populado por `RLSContextMiddleware` (api/core/bootstrap.py) a
partir do JWT. Enquanto a conexão for `postgres` (BYPASSRLS), o `SET LOCAL` é
inócuo (a RLS não se aplica ao role); o isolamento real liga quando o backend
passar a conectar como `app_orgconc` (NOBYPASSRLS). Ver db/rls/README.md.
"""
from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

# org_id (uuid em str) do request atual. None = sem tenant (estado atual).
_org_atual: ContextVar[Optional[str]] = ContextVar("orgconc_org_id", default=None)


def set_org_context(org_id: Optional[str]) -> Token:
    """Define o org_id do request atual (a partir do token autenticado).

    Devolve o Token do ContextVar para que o chamador possa restaurar o valor
    anterior com `reset_org_context` (evita vazamento entre requests).
    """
    return _org_atual.set(str(org_id) if org_id else None)


def reset_org_context(token: Token) -> None:
    """Restaura o org_id anterior (par de `set_org_context`)."""
    _org_atual.reset(token)


def get_org_context() -> Optional[str]:
    """org_id do request atual, ou None se sem tenant."""
    return _org_atual.get()


async def aplicar_rls(session: AsyncSession) -> None:
    """Aplica `SET LOCAL app.org_id` na sessão a partir do contexto (one-shot).

    Mantido por compat; o caminho normal é o listener `after_begin` abaixo, que
    cobre múltiplas transações por request. No-op sem org no contexto.
    """
    org = _org_atual.get()
    if not org:
        return
    await session.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": org})


@event.listens_for(Session, "after_begin")
def _set_org_no_begin(session, transaction, connection) -> None:
    """Em cada início de transação, propaga o org do contexto para `app.org_id`.

    Registrado na classe Session genérica (cobre as AsyncSession, que rodam sobre
    uma Session sync). Só age havendo org no contextvar — caso contrário não toca
    a conexão (sessões de auth/login, sem org, seguem sem GUC). `is_local=true`
    escopa o valor à transação corrente.
    """
    org = _org_atual.get()
    if org:
        connection.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": org})
