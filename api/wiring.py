"""Dependency Injection — factories que FastAPI usa em Depends().

Centraliza o wiring infra -> usecase. Routers nao instanciam nada;
apenas declaram a dependencia.

Exemplo:
    @router.post("/clientes")
    async def criar(payload: X, uc: CriarClienteUseCase = Depends(get_criar_cliente_uc)):
        ...
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.infra.repositories import (
    ClienteRepositorySQL,
    ConciliacaoRepositorySQL,
    RefreshTokenRepositorySQL,
)
from api.usecases import (
    CriarClienteUseCase,
    ListarClientesUseCase,
    ListarConciliacoesUseCase,
)


# ── Sessao DB ────────────────────────────────────────────────────────────────

async def get_db_session() -> AsyncIterator:
    """Yield uma AsyncSession. 503 se DB nao configurado.

    Use como Depends para qualquer endpoint que precise do banco.
    """
    if not DB_DISPONIVEL or SessionLocal is None:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as session:
        yield session


# ── Repositories ────────────────────────────────────────────────────────────

def get_cliente_repo(db=Depends(get_db_session)) -> ClienteRepositorySQL:
    return ClienteRepositorySQL(db)


def get_conciliacao_repo(db=Depends(get_db_session)) -> ConciliacaoRepositorySQL:
    return ConciliacaoRepositorySQL(db)


def get_refresh_token_repo(db=Depends(get_db_session)) -> RefreshTokenRepositorySQL:
    return RefreshTokenRepositorySQL(db)


# ── Use cases ───────────────────────────────────────────────────────────────

def get_criar_cliente_uc(repo: ClienteRepositorySQL = Depends(get_cliente_repo)) -> CriarClienteUseCase:
    return CriarClienteUseCase(repo)


def get_listar_clientes_uc(
    repo: ClienteRepositorySQL = Depends(get_cliente_repo),
) -> ListarClientesUseCase:
    return ListarClientesUseCase(repo)


def get_listar_conciliacoes_uc(
    repo: ConciliacaoRepositorySQL = Depends(get_conciliacao_repo),
) -> ListarConciliacoesUseCase:
    return ListarConciliacoesUseCase(repo)
