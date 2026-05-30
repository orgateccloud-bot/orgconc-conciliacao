"""Router /v1/jobs — polling de jobs assincronos enfileirados via Arq."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.db import jobs as jobs_repo
from api.infra.queue import enqueue_job
from api.services.auth import TokenPayload, current_user

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(current_user)])


def _serializar(j) -> dict:
    return {
        "id": str(j.id),
        "tipo": j.tipo,
        "status": j.status,
        "progresso": j.progresso,
        "input": json.loads(j.input_json) if j.input_json else None,
        "output": json.loads(j.output_json) if j.output_json else None,
        "erro": j.erro,
        "criado_em": j.criado_em.isoformat() if j.criado_em else None,
        "iniciado_em": j.iniciado_em.isoformat() if j.iniciado_em else None,
        "finalizado_em": j.finalizado_em.isoformat() if j.finalizado_em else None,
    }


@router.post("", status_code=202)
@limiter.limit("20/minute")
async def enfileirar_job(
    request: Request,
    payload: dict,
    user: TokenPayload = Depends(current_user),
):
    """Enfileira um job. Retorna 202 + job_id imediatamente.

    Payload:
        { "tipo": "conciliar_ofx" | "ping", "input": {...} }

    Tipos suportados:
    - ping (debug, sem input)
    - conciliar_ofx (logica plugada no item 13 fase 2)
    """
    if not DB_DISPONIVEL or SessionLocal is None:
        raise HTTPException(503, "Jobs indisponiveis (DB nao configurado)")
    tipo = (payload.get("tipo") or "").strip()
    if tipo not in ("ping", "conciliar_ofx"):
        raise HTTPException(400, f"Tipo invalido: {tipo}")

    input_data = payload.get("input") or {}
    async with SessionLocal() as db:
        job = await jobs_repo.criar(db, sub=user.sub, tipo=tipo, input_data=input_data)

    # Enfileira no Arq (worker pega async)
    funcao_arq = "conciliar_ofx_task" if tipo == "conciliar_ofx" else "ping_task"
    try:
        await enqueue_job(funcao_arq, str(job.id), job_id=job.id)
    except Exception as exc:
        # Marca como failed e retorna 502 — nao deixa job orfao na tabela
        async with SessionLocal() as db:
            await jobs_repo.marcar_failed(db, job.id, f"enqueue_failed: {exc}")
        raise HTTPException(502, "Falha ao enfileirar — Redis indisponivel?") from exc

    return {
        "id": str(job.id),
        "tipo": tipo,
        "status": "queued",
        "polling_url": f"/v1/jobs/{job.id}",
    }


@router.get("/{job_id}")
@limiter.limit("60/minute")
async def buscar_job(
    request: Request,
    job_id: str,
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL or SessionLocal is None:
        raise HTTPException(503, "Jobs indisponiveis")
    try:
        jid = uuid.UUID(job_id)
    except ValueError as e:
        raise HTTPException(400, "ID invalido") from e
    async with SessionLocal() as db:
        job = await jobs_repo.buscar(db, jid)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job.sub != user.sub:
        # Defesa em profundidade — nao vaza existencia de job de outro user
        raise HTTPException(404, "Job nao encontrado")
    return _serializar(job)


@router.get("")
@limiter.limit("30/minute")
async def listar_jobs(
    request: Request,
    limit: int = 50,
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL or SessionLocal is None:
        raise HTTPException(503, "Jobs indisponiveis")
    async with SessionLocal() as db:
        jobs = await jobs_repo.listar_do_sub(db, user.sub, limit=limit)
    return [_serializar(j) for j in jobs]


@router.post("/{job_id}/cancel")
@limiter.limit("10/minute")
async def cancelar_job(
    request: Request,
    job_id: str,
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL or SessionLocal is None:
        raise HTTPException(503, "Jobs indisponiveis")
    try:
        jid = uuid.UUID(job_id)
    except ValueError as e:
        raise HTTPException(400, "ID invalido") from e
    async with SessionLocal() as db:
        job = await jobs_repo.buscar(db, jid)
        if not job or job.sub != user.sub:
            raise HTTPException(404, "Job nao encontrado")
        await jobs_repo.marcar_cancelled(db, jid)
    return {"id": str(jid), "status": "cancelled"}
