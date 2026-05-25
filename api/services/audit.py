"""Servico de trilha de auditoria com hash chain (sha256 + prev_hash).

Cada evento e encadeado ao anterior via prev_hash, formando uma cadeia
verificavel (genesis = '0' * 64). Permite provar integridade sem
assinatura criptografica.

Uso:
    from api.services.audit import registrar_audit
    await registrar_audit(
        db,
        action="conciliacao.criar",
        resource_type="conciliacao",
        resource_id=report_id,
        payload={"modo": "claude_llm", "total_tx": 42},
        actor=user,
    )
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AuditEvent
from api.services.auth import TokenPayload
from api.services.logging_estruturado import request_id_var

log = logging.getLogger("orgconc.audit")

GENESIS_HASH = "0" * 64


def calcular_hash(payload: Optional[dict[str, Any]]) -> str:
    """SHA256 do JSON canonico (sort_keys garante determinismo)."""
    raw = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _buscar_ultimo_hash(db: AsyncSession) -> str:
    q = select(AuditEvent.payload_hash).order_by(AuditEvent.ts.desc()).limit(1)
    result = await db.execute(q)
    last = result.scalar_one_or_none()
    return last or GENESIS_HASH


async def registrar_audit(
    db: AsyncSession,
    *,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    actor: Optional[TokenPayload] = None,
) -> AuditEvent:
    """Insere um evento na cadeia. NAO faz commit — caller decide a transacao.

    `payload` deve conter apenas dados estruturados (sem PII bruta).
    `actor` vem do current_user dependency; se None, registra como sistema.
    """
    prev_hash = await _buscar_ultimo_hash(db)
    payload_hash = calcular_hash(payload)
    rid = request_id_var.get()
    if rid == "-":
        rid = None

    event = AuditEvent(
        actor_email=getattr(actor, "email", None) if actor else None,
        actor_sub=getattr(actor, "sub", None) if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        payload_hash=payload_hash,
        prev_hash=prev_hash,
        request_id=rid,
    )
    db.add(event)
    await db.flush()
    return event


async def gravar_audit_independente(
    *,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    actor: Optional[TokenPayload] = None,
) -> Optional[AuditEvent]:
    """Grava um evento abrindo sessao propria — nao bloqueia o handler chamador.

    Silencioso em caso de erro (DB offline, etc) — apenas loga. Usado nos
    routers (login, conciliar, clientes) para auditar sem interferir
    na transacao principal.
    """
    try:
        from api.core.config import DB_DISPONIVEL, SessionLocal
        if not DB_DISPONIVEL or SessionLocal is None:
            return None
        async with SessionLocal() as db:
            ev = await registrar_audit(
                db,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                payload=payload,
                actor=actor,
            )
            await db.commit()
            return ev
    except Exception:
        log.exception("Falha ao gravar audit event %s", action)
        return None


def verificar_cadeia(eventos: list[AuditEvent]) -> tuple[bool, Optional[str]]:
    """Valida que cada evento aponta para o hash do anterior.

    Retorna (True, None) se cadeia integra ou (False, motivo) se quebrada.
    Eventos devem vir ordenados por ts ascendente.
    """
    esperado = GENESIS_HASH
    for ev in eventos:
        if ev.prev_hash != esperado:
            return False, f"prev_hash divergente em {ev.id}: esperado {esperado[:8]}, encontrado {ev.prev_hash[:8]}"
        recalculado = calcular_hash(ev.payload)
        if ev.payload_hash != recalculado:
            return False, f"payload_hash divergente em {ev.id}: payload modificado apos insercao"
        esperado = ev.payload_hash
    return True, None
