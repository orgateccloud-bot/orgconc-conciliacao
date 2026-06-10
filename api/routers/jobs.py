"""Router /jobs — status e resultado da fila assíncrona (P1 #9).

Submissão é feita pelos endpoints de domínio (ex.: POST /fiscal/laudo/async);
aqui ficam o polling e o download. A RLS (org_isolation) garante que o usuário
só enxerga jobs da própria org — job alheio simplesmente não existe (404).
"""
from __future__ import annotations

import logging
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.services.auth import TokenPayload, current_user

router = APIRouter(tags=["jobs"], prefix="/jobs")
log = logging.getLogger("orgconc.jobs")

_CAMPOS_STATUS = ("id", "tipo", "status", "erro", "tentativas",
                  "criado_em", "iniciado_em", "concluido_em",
                  "resultado_nome", "resultado_mime")


def _exigir_db() -> None:
    if not DB_DISPONIVEL or SessionLocal is None:
        raise HTTPException(503, "Fila de jobs requer banco de dados configurado.")


def _job_para_dict(row) -> dict:
    d = dict(zip(_CAMPOS_STATUS, row))
    d["id"] = str(d["id"])
    for k in ("criado_em", "iniciado_em", "concluido_em"):
        d[k] = d[k].isoformat() if d[k] else None
    return d


def _parse_job_id(job_id: str) -> _uuid.UUID:
    try:
        return _uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(404, "Job não encontrado.")


def _select_status_cols():
    from api.db.models import Job

    return select(Job.id, Job.tipo, Job.status, Job.erro, Job.tentativas,
                  Job.criado_em, Job.iniciado_em, Job.concluido_em,
                  Job.resultado_nome, Job.resultado_mime)


@router.get("")
@limiter.limit("30/minute")
async def listar_jobs(request: Request, user: TokenPayload = Depends(current_user)):
    """Últimos 20 jobs da org (sem blobs)."""
    _exigir_db()
    from api.db.models import Job

    async with SessionLocal() as db:
        rows = (await db.execute(
            _select_status_cols().order_by(Job.criado_em.desc()).limit(20)
        )).all()
    return {"total": len(rows), "jobs": [_job_para_dict(r) for r in rows]}


@router.get("/{job_id}")
@limiter.limit("60/minute")
async def status_job(request: Request, job_id: str,
                     user: TokenPayload = Depends(current_user)):
    """Status de 1 job (polling). 404 também para job de outra org (RLS)."""
    _exigir_db()
    from api.db.models import Job

    jid = _parse_job_id(job_id)
    async with SessionLocal() as db:
        row = (await db.execute(
            _select_status_cols().where(Job.id == jid)
        )).first()
    if row is None:
        raise HTTPException(404, "Job não encontrado.")
    return _job_para_dict(row)


@router.get("/{job_id}/resultado")
@limiter.limit("30/minute")
async def resultado_job(request: Request, job_id: str,
                        user: TokenPayload = Depends(current_user)):
    """Baixa o arquivo gerado pelo job (409 enquanto não concluído)."""
    _exigir_db()
    from api.db.models import Job

    jid = _parse_job_id(job_id)
    async with SessionLocal() as db:
        row = (await db.execute(
            select(Job.status, Job.resultado, Job.resultado_nome,
                   Job.resultado_mime, Job.erro).where(Job.id == jid)
        )).first()
    if row is None:
        raise HTTPException(404, "Job não encontrado.")
    status, resultado, nome, mime, erro = row
    if status == "ERRO":
        raise HTTPException(422, f"Job falhou: {erro or 'erro desconhecido'}")
    if status != "CONCLUIDO" or resultado is None:
        raise HTTPException(409, f"Job ainda não concluído (status: {status}).")
    disposition = "inline" if (mime or "").startswith("text/html") else "attachment"
    return Response(
        content=resultado,
        media_type=mime or "application/octet-stream",
        headers={"Content-Disposition": f'{disposition}; filename="{nome or "resultado"}"'},
    )
