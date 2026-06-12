"""Contexto de RLS por organização (tenant = org_id).

Liga o usuário autenticado à sessão de banco: guarda o org_id do request num
ContextVar (isolado por task no event loop) e o aplica via `SET LOCAL app.org_id`
no início de CADA transação (listener `after_begin`), para a policy
`org_isolation` (db/rls/org_isolation.sql) filtrar as linhas no banco.

O contextvar é populado por `RLSContextMiddleware` (api/core/bootstrap.py) a
partir do JWT. Em produção o backend conecta como `app_orgconc` (NOBYPASSRLS)
desde 2026-06-07 — o `SET LOCAL` aqui é o que efetivamente isola os tenants
(policy fail-closed: sem `app.org_id` setado → zero linhas). Em dev com a
conexão `postgres` (BYPASSRLS) o SET é inócuo. Ver db/rls/README.md.
"""
from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

# org_id (uuid em str) do request atual. None = sem tenant (estado atual).
_org_atual: ContextVar[Optional[str]] = ContextVar("orgconc_org_id", default=None)
# Superadmin (leitura cross-org): só o admin por env. Default False.
_superadmin_atual: ContextVar[bool] = ContextVar("orgconc_superadmin", default=False)
# Worker de jobs (fila P1 #9): habilita a policy worker_access na tabela jobs
# (claim/finalização cross-org). Só o loop do worker seta — nunca um request.
_worker_atual: ContextVar[bool] = ContextVar("orgconc_worker", default=False)


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


def set_superadmin_context(valor: bool) -> Token:
    """Marca o request como superadmin (leitura cross-org). Par: reset_superadmin_context."""
    return _superadmin_atual.set(bool(valor))


def reset_superadmin_context(token: Token) -> None:
    _superadmin_atual.reset(token)


def get_superadmin_context() -> bool:
    return _superadmin_atual.get()


def set_worker_context(valor: bool) -> Token:
    """Marca a task atual como worker de jobs (policy worker_access da tabela
    jobs). Par: reset_worker_context. Restrito ao loop de api/services/job_queue."""
    return _worker_atual.set(bool(valor))


def reset_worker_context(token: Token) -> None:
    _worker_atual.reset(token)


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
    if _superadmin_atual.get():
        # Habilita a policy superadmin_read (FOR SELECT) — leitura cross-org.
        connection.execute(text("SELECT set_config('app.superadmin', 'on', true)"))
    if _worker_atual.get():
        # Habilita a policy worker_access da tabela jobs (claim cross-org do worker).
        connection.execute(text("SELECT set_config('app.worker', 'on', true)"))
