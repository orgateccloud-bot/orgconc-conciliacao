"""Router /conciliacoes — listagem e busca via use case."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from api.core.rate_limit import limiter
from api.schemas_responses import ConciliacaoListItem
from api.services.auth import current_user
from api.usecases import ListarConciliacoesInput, ListarConciliacoesUseCase
from api.wiring import get_conciliacao_repo, get_listar_conciliacoes_uc

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
        "criado_em": c.criado_em.isoformat() if c.criado_em else None,
        "exports": {
            "html": f"/export/html/{c.report_id}",
            "xlsx": f"/export/xlsx/{c.report_id}",
            "pdf": f"/export/pdf/{c.report_id}",
        },
    }


@router.get("", response_model=list[ConciliacaoListItem])
@limiter.limit("30/minute")
async def listar(
    request: Request,
    cliente_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    uc: ListarConciliacoesUseCase = Depends(get_listar_conciliacoes_uc),
):
    cid = None
    if cliente_id:
        try:
            cid = uuid.UUID(cliente_id)
        except ValueError as e:
            raise HTTPException(400, "cliente_id invalido") from e
    conciliacoes = await uc.execute(ListarConciliacoesInput(cliente_id=cid, limit=limit, offset=offset))
    return [_serializar(c) for c in conciliacoes]


@router.get("/por-cliente/{cliente_id}", response_model=list[ConciliacaoListItem])
@limiter.limit("30/minute")
async def listar_por_cliente(
    request: Request,
    cliente_id: str,
    limit: int = 50,
    offset: int = 0,
    uc: ListarConciliacoesUseCase = Depends(get_listar_conciliacoes_uc),
):
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError as e:
        raise HTTPException(400, "cliente_id invalido") from e
    conciliacoes = await uc.execute(ListarConciliacoesInput(cliente_id=cid, limit=limit, offset=offset))
    return [_serializar(c) for c in conciliacoes]


@router.get("/{report_id}", response_model=ConciliacaoListItem)
@limiter.limit("30/minute")
async def buscar(
    request: Request,
    report_id: str,
    repo=Depends(get_conciliacao_repo),
):
    c = await repo.buscar_por_report_id(report_id)
    if not c:
        raise HTTPException(404, "Conciliacao nao encontrada")
    return _serializar(c)
