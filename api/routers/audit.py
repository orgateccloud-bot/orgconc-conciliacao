"""Trilha de auditoria — eventos com hash chain."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.db import audit_events as crud_audit
from api.db.models import AuditEvent
from api.services.audit import calcular_hash, verificar_cadeia
from api.services.auth import current_user
from api.services.logging_estruturado import mask_pii

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(current_user)])


def _mascarar_payload(payload: Optional[dict]) -> Optional[dict]:
    """Aplica mask_pii em strings dentro do payload, recursivamente."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        return {k: _mascarar_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_mascarar_payload(v) for v in payload]
    if isinstance(payload, str):
        return mask_pii(payload)
    return payload


def _serializar(ev: AuditEvent, *, com_payload: bool = False) -> dict:
    out = {
        "id": str(ev.id),
        "ts": ev.ts.isoformat() if ev.ts else None,
        "actor_email": mask_pii(ev.actor_email) if ev.actor_email else None,
        "actor_sub": ev.actor_sub,
        "action": ev.action,
        "resource_type": ev.resource_type,
        "resource_id": ev.resource_id,
        "payload_hash": ev.payload_hash,
        "prev_hash": ev.prev_hash,
        "payload_hash_short": ev.payload_hash[:8] if ev.payload_hash else None,
        "request_id": ev.request_id,
    }
    if com_payload:
        out["payload"] = _mascarar_payload(ev.payload)
        # Verifica integridade do hash do evento isolado
        recalculado = calcular_hash(ev.payload)
        out["payload_hash_valid"] = recalculado == ev.payload_hash
    return out


@router.get("/timeline")
@limiter.limit("60/minute")
async def listar_timeline(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor_email: Optional[str] = None,
    resource_type: Optional[str] = None,
):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as db:
        eventos = await crud_audit.listar_eventos(
            db,
            limit=limit,
            offset=offset,
            actor_email=actor_email,
            resource_type=resource_type,
        )
        total = await crud_audit.contar_eventos(db)
    # Verifica integridade da janela em ordem cronologica
    em_ordem = list(reversed(eventos))
    cadeia_ok, motivo = verificar_cadeia(em_ordem)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "cadeia_integra": cadeia_ok,
        "cadeia_motivo": motivo,
        "eventos": [_serializar(e) for e in eventos],
    }


@router.get("/eventos/{evento_id}")
@limiter.limit("60/minute")
async def buscar_evento(request: Request, evento_id: str):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    try:
        eid = uuid.UUID(evento_id)
    except ValueError:
        raise HTTPException(400, "evento_id invalido")
    async with SessionLocal() as db:
        ev = await db.get(AuditEvent, eid)
    if not ev:
        raise HTTPException(404, "Evento nao encontrado")
    return _serializar(ev, com_payload=True)
