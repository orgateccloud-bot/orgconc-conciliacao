"""Transacoes cross-conciliacao para o dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.db import metrics as crud_metrics
from api.services.auth import TokenPayload, current_user, escopo_cliente_listagem

router = APIRouter(prefix="/transacoes", tags=["transacoes"], dependencies=[Depends(current_user)])


def _serializar(t) -> dict:
    return {
        "id": str(t.id),
        "conciliacao_id": str(t.conciliacao_id) if t.conciliacao_id else None,
        "data_lancamento": t.data_lancamento.isoformat() if t.data_lancamento else None,
        "valor": float(t.valor) if t.valor is not None else None,
        "memo": t.memo,
        "categoria": t.categoria,
        "banco": t.banco,
        "tipo": t.tipo,
        "eh_anomalia": bool(t.eh_anomalia),
        "criado_em": t.criado_em.isoformat() if t.criado_em else None,
    }


@router.get("/recentes")
@limiter.limit("60/minute")
async def listar_recentes(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    # Escopo de tenant centralizado (nega anonymous em prod; user → próprio cliente)
    escopo = escopo_cliente_listagem(user)
    tenant_id = None
    if escopo:
        import uuid as _uuid
        try:
            tenant_id = _uuid.UUID(escopo)
        except ValueError:
            pass
    async with SessionLocal() as db:
        rows = await crud_metrics.listar_transacoes_recentes(db, limit=limit, cliente_id=tenant_id)
    return [_serializar(t) for t in rows]
