from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.db import conciliacoes as crud_conc
from api.infra.repositories.conciliacoes import ConciliacaoRepositorySQL
from api.services.auth import current_user
from api.usecases.listar_conciliacoes import ListarConciliacoesInput, ListarConciliacoesUseCase

router = APIRouter(prefix="/conciliacoes", tags=["conciliacoes"], dependencies=[Depends(current_user)])


def _serializar(c) -> dict:
    return {
        "id": str(c.id),
        "report_id": c.report_id,
        "cliente_id": str(c.cliente_id) if c.cliente_id else None,
        "modo": c.modo,
        "total_transacoes": c.total_transacoes,
        "total_anomalias": c.total_anomalias,
        "periodo_inicio": c.periodo_inicio.isoformat() if c.periodo_inicio else None,
        "periodo_fim": c.periodo_fim.isoformat() if c.periodo_fim else None,
        "criado_em": c.criado_em.isoformat(),
        "exports": {
            "html": f"/export/html/{c.report_id}",
            "xlsx": f"/export/xlsx/{c.report_id}",
            "pdf": f"/export/pdf/{c.report_id}",
        },
    }


@router.get("")
@limiter.limit("30/minute")
async def listar(request: Request, cliente_id: str | None = None, limit: int = 50, offset: int = 0):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    cid = None
    if cliente_id:
        try:
            cid = uuid.UUID(cliente_id)
        except ValueError:
            raise HTTPException(400, "cliente_id invalido")
    async with SessionLocal() as db:
        uc = ListarConciliacoesUseCase(ConciliacaoRepositorySQL(db))
        rows = await uc.execute(ListarConciliacoesInput(cliente_id=cid, limit=min(limit, 100), offset=offset))
    return [_serializar(c) for c in rows]


@router.get("/por-cliente/{cliente_id}")
@limiter.limit("30/minute")
async def listar_por_cliente(request: Request, cliente_id: str, limit: int = 50, offset: int = 0):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "cliente_id invalido")
    async with SessionLocal() as db:
        uc = ListarConciliacoesUseCase(ConciliacaoRepositorySQL(db))
        rows = await uc.execute(ListarConciliacoesInput(cliente_id=cid, limit=min(limit, 100), offset=offset))
    return [_serializar(c) for c in rows]


@router.get("/{report_id}")
@limiter.limit("30/minute")
async def buscar(request: Request, report_id: str):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as db:
        c = await crud_conc.buscar_por_report_id(db, report_id)
    if not c:
        raise HTTPException(404, "Conciliacao nao encontrada")
    return _serializar(c)
