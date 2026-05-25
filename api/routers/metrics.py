"""Metricas agregadas para o dashboard.

Endpoints:
- GET /metrics/dashboard-bundle  : tudo em 1 request (cache 60s/user)
- GET /metrics/trend             : serie temporal
- GET /metrics/distribuicao      : por modo de conciliacao
- GET /metrics/heatmap           : volume diario

Cache em memoria para evitar 10+ round-trips quando o dashboard monta.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.db import metrics as crud_metrics
from api.services.auth import TokenPayload, current_user

router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(current_user)])

_CACHE_TTL_S = 60
_bundle_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _check_db():
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")


@router.get("/dashboard-bundle")
@limiter.limit("60/minute")
async def dashboard_bundle(
    request: Request,
    periodo: int = Query(30, ge=1, le=365),
    user: TokenPayload = Depends(current_user),
):
    """Bundle de metricas para mount do dashboard. Cache 60s por (user, periodo)."""
    _check_db()
    cache_key = f"{user.sub}:{periodo}"
    agora = time.time()
    cached = _bundle_cache.get(cache_key)
    if cached and agora - cached[0] < _CACHE_TTL_S:
        return cached[1]

    async with SessionLocal() as db:
        kpis = await crud_metrics.agregar_kpis(db, periodo_dias=periodo)
        trend = await crud_metrics.serie_temporal(db, periodo_dias=periodo)
        distribuicao = await crud_metrics.distribuicao_modo(db, periodo_dias=periodo)
        heatmap = await crud_metrics.heatmap_diario(db, periodo_dias=min(periodo * 4, 365))

    bundle = {
        "kpis": kpis,
        "trend": trend,
        "distribuicao": distribuicao,
        "heatmap": heatmap,
        "gerado_em": agora,
        "cache_ttl_s": _CACHE_TTL_S,
    }
    _bundle_cache[cache_key] = (agora, bundle)
    return bundle


@router.get("/trend")
@limiter.limit("60/minute")
async def trend(
    request: Request,
    periodo: int = Query(30, ge=1, le=365),
):
    _check_db()
    async with SessionLocal() as db:
        return await crud_metrics.serie_temporal(db, periodo_dias=periodo)


@router.get("/distribuicao")
@limiter.limit("60/minute")
async def distribuicao(
    request: Request,
    periodo: int = Query(30, ge=1, le=365),
):
    _check_db()
    async with SessionLocal() as db:
        return await crud_metrics.distribuicao_modo(db, periodo_dias=periodo)


@router.get("/heatmap")
@limiter.limit("60/minute")
async def heatmap(
    request: Request,
    periodo: int = Query(120, ge=7, le=365),
):
    _check_db()
    async with SessionLocal() as db:
        return await crud_metrics.heatmap_diario(db, periodo_dias=periodo)


_trust_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_TRUST_TTL_S = 300
_modelos_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_MODELOS_TTL_S = 60


@router.get("/modelos")
@limiter.limit("60/minute")
async def modelos(
    request: Request,
    periodo: int = Query(30, ge=1, le=365),
):
    """Uso e latencia media por modo de conciliacao."""
    _check_db()
    cache_key = f"modelos:{periodo}"
    agora = time.time()
    cached = _modelos_cache.get(cache_key)
    if cached and agora - cached[0] < _MODELOS_TTL_S:
        return cached[1]
    async with SessionLocal() as db:
        result = await crud_metrics.performance_modelos(db, periodo_dias=periodo)
    _modelos_cache[cache_key] = (agora, result)
    return result


@router.get("/trust-score")
@limiter.limit("60/minute")
async def trust_score(
    request: Request,
    periodo: int = Query(30, ge=7, le=365),
):
    """Score derivado 0-100 (cache 5min global). Sem dados retorna score=0 + descricao."""
    _check_db()
    cache_key = f"trust:{periodo}"
    agora = time.time()
    cached = _trust_cache.get(cache_key)
    if cached and agora - cached[0] < _TRUST_TTL_S:
        return cached[1]
    async with SessionLocal() as db:
        resultado = await crud_metrics.calcular_trust_score(db, periodo_dias=periodo)
    _trust_cache[cache_key] = (agora, resultado)
    return resultado


def invalidar_cache_metrics(user_sub: str | None = None) -> None:
    """Invalida cache; util quando nova conciliacao e criada."""
    if user_sub is None:
        _bundle_cache.clear()
        return
    for k in list(_bundle_cache):
        if k.startswith(f"{user_sub}:"):
            del _bundle_cache[k]
