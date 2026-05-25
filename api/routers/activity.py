"""Feed de atividade — view amigavel sobre audit_events."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.db import audit_events as crud_audit
from api.services.auth import current_user
from api.services.logging_estruturado import mask_pii

router = APIRouter(prefix="/activity", tags=["activity"], dependencies=[Depends(current_user)])


_TITULOS = {
    "login.success":      "Login bem-sucedido",
    "conciliacao.criar":  "Conciliacao criada",
    "cliente.criar":      "Cliente cadastrado",
    "cliente.atualizar":  "Cliente atualizado",
}

_SEVERIDADES = {
    "login.success":      "info",
    "conciliacao.criar":  "success",
    "cliente.criar":      "info",
    "cliente.atualizar":  "info",
}


@router.get("/feed")
@limiter.limit("60/minute")
async def feed(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as db:
        eventos = await crud_audit.listar_eventos(db, limit=limit)
    return [
        {
            "id": str(ev.id),
            "ts": ev.ts.isoformat() if ev.ts else None,
            "titulo": _TITULOS.get(ev.action, ev.action),
            "severidade": _SEVERIDADES.get(ev.action, "info"),
            "ator": mask_pii(ev.actor_email) if ev.actor_email else (ev.actor_sub or "sistema"),
            "resource_id": ev.resource_id,
        }
        for ev in eventos
    ]
