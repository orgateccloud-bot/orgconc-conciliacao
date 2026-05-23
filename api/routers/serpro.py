from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from api.core.rate_limit import limiter
from api.schemas import ConsultaCNPJRequest, ConsultaCPFRequest
from api.services import serpro_consulta as serpro
from api.services.auth import current_user

router = APIRouter(prefix="/serpro", tags=["serpro"], dependencies=[Depends(current_user)])


@router.post("/cpf")
@limiter.limit("10/minute")
async def consultar_cpf(request: Request, payload: ConsultaCPFRequest):
    if not serpro.disponivel():
        raise HTTPException(503, "Integracao SERPRO nao configurada")
    return await serpro.consultar_cpf_async(payload.cpf)


@router.post("/cnpj")
@limiter.limit("10/minute")
async def consultar_cnpj(request: Request, payload: ConsultaCNPJRequest):
    if not serpro.disponivel():
        raise HTTPException(503, "Integracao SERPRO nao configurada")
    return await serpro.consultar_cnpj_async(payload.cnpj)
