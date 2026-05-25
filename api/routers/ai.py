"""Insights da IA (Claude) com cache hibrido em Postgres."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.services.ai_insights import get_insights
from api.services.auth import TokenPayload, current_user

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(current_user)])


@router.get("/insights/dashboard")
@limiter.limit("30/minute")
async def insights_dashboard(
    request: Request,
    periodo: int = Query(30, ge=7, le=365),
    refresh: bool = Query(False, description="Forca nova chamada Claude (ignora cache)"),
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as db:
        result = await get_insights(
            db, actor_sub=user.sub, periodo_dias=periodo, refresh=refresh
        )
    return result
