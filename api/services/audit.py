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
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AuditEvent, _now
from api.services.auth import TokenPayload
from api.services.logging_estruturado import request_id_var

log = logging.getLogger("orgconc.audit")

GENESIS_HASH = "0" * 64

# Namespace fixo p/ o advisory lock da cadeia de auditoria (1a chave do
# pg_advisory_xact_lock(int4, int4)). Evita colidir com locks de outros modulos.
_LOCK_NAMESPACE_AUDIT = 0x4F43  # "OC"


def _chave_lock_cadeia(org_id: Optional[str]) -> int:
    """Deriva uma chave int32 estavel p/ o advisory lock da cadeia da org.

    org_id None (cadeia do sistema) usa 0. Java-style hash truncado a int32
    com sinal (faixa aceita por pg_advisory_xact_lock).
    """
    if org_id is None:
        return 0
    h = 0
    for ch in str(org_id):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    # Converte para int32 com sinal.
    return h - 0x100000000 if h >= 0x80000000 else h


def calcular_hash(payload: Optional[dict[str, Any]]) -> str:
    """SHA256 do JSON canonico do payload (sort_keys garante determinismo).

    Mantido por compatibilidade — `calcular_hash_evento` cobre tambem os
    metadados do evento (action, actor, ts, org_id, prev_hash).
    """
    raw = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def calcular_hash_evento(
    *,
    action: str,
    resource_type: Optional[str],
    resource_id: Optional[str],
    actor_sub: Optional[str],
    actor_email: Optional[str],
    ts: Optional[datetime],
    org_id: Optional[str],
    payload: Optional[dict[str, Any]],
    prev_hash: str,
) -> str:
    """SHA256 do JSON canonico dos metadados + payload + prev_hash do evento.

    O hash passa a cobrir os campos imutaveis do evento (#2): adulterar
    action/actor/ts/org_id apos a insercao quebra a verificacao da cadeia,
    nao so a edicao do payload. `ts` e serializado em ISO-8601 (UTC).
    """
    doc = {
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "actor_sub": actor_sub,
        "actor_email": actor_email,
        "ts": ts.isoformat() if ts is not None else None,
        "org_id": str(org_id) if org_id is not None else None,
        "payload": payload or {},
        "prev_hash": prev_hash,
    }
    raw = json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _buscar_ultimo_hash(db: AsyncSession, org_id: Optional[str]) -> str:
    """Ultimo hash da cadeia DA ORGANIZACAO, serializado por advisory lock (#1, #4).

    A cadeia e por org: filtra por org_id (NULL = cadeia do sistema). Dois
    mecanismos garantem que writers concorrentes nao forkem a cadeia:

    1. `pg_advisory_xact_lock(ns, org)`: serializa por org JA na leitura do
       ultimo hash. Cobre ate o caso genesis (cadeia vazia) — `with_for_update`
       sozinho nao trava linha inexistente, logo dois primeiros writers poderiam
       ambos ler vazio e usar GENESIS. O lock e transacional (solta no commit).
    2. `with_for_update()`: trava a ultima linha existente (defesa em camadas).
    """
    await db.execute(
        select(func.pg_advisory_xact_lock(_LOCK_NAMESPACE_AUDIT, _chave_lock_cadeia(org_id)))
    )
    q = (
        select(AuditEvent)
        .order_by(AuditEvent.ts.desc())
        .limit(1)
        .with_for_update()
    )
    if org_id is None:
        q = q.where(AuditEvent.org_id.is_(None))
    else:
        q = q.where(AuditEvent.org_id == org_id)
    result = await db.execute(q)
    last = result.scalar_one_or_none()
    return last.payload_hash if last is not None else GENESIS_HASH


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

    Atomicidade (#1, #4): o SELECT do ultimo hash (com FOR UPDATE, filtrado
    pela org do actor) e o INSERT ficam na MESMA transacao do caller — sem
    commit no meio. Writers concorrentes da mesma org serializam, evitando
    fork da cadeia. O hash cobre os metadados do evento (#2).
    """
    org_id = getattr(actor, "org_id", None) if actor else None
    actor_email = getattr(actor, "email", None) if actor else None
    actor_sub = getattr(actor, "sub", None) if actor else None

    prev_hash = await _buscar_ultimo_hash(db, org_id)
    ts = _now()
    payload_hash = calcular_hash_evento(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_sub=actor_sub,
        actor_email=actor_email,
        ts=ts,
        org_id=org_id,
        payload=payload,
        prev_hash=prev_hash,
    )
    rid = request_id_var.get()
    if rid == "-":
        rid = None

    event = AuditEvent(
        ts=ts,
        org_id=org_id,
        actor_email=actor_email,
        actor_sub=actor_sub,
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


def hash_evento(ev: AuditEvent) -> str:
    """Recalcula o hash de UM evento a partir dos seus campos (helper p/ a UI).

    Usado pelo endpoint /audit para sinalizar se o hash gravado bate com o
    recalculo dos campos atuais (deteccao de adulteracao por evento).
    """
    return calcular_hash_evento(
        action=ev.action,
        resource_type=ev.resource_type,
        resource_id=ev.resource_id,
        actor_sub=ev.actor_sub,
        actor_email=ev.actor_email,
        ts=ev.ts,
        org_id=getattr(ev, "org_id", None),
        payload=ev.payload,
        prev_hash=ev.prev_hash,
    )


def verificar_cadeia(
    eventos: list[AuditEvent], *, exigir_genesis: bool = True
) -> tuple[bool, Optional[str]]:
    """Valida que cada evento aponta para o hash do anterior.

    Retorna (True, None) se cadeia integra ou (False, motivo) se quebrada.
    Eventos devem vir ordenados por ts ascendente.

    A cadeia e POR ORGANIZACAO (#3/#4): cada org tem seu proprio encadeamento
    a partir do GENESIS. Eventos de orgs distintas (incluindo a cadeia do
    sistema, org_id NULL) sao validados independentemente. O hash recalculado
    cobre os metadados do evento (#2), nao so o payload.

    `exigir_genesis=True` (default): a lista DEVE comecar no genesis de cada org
    (verificacao da cadeia inteira). Numa JANELA paginada (timeline) passe
    `exigir_genesis=False`: o 1o evento de cada org na janela e ancorado pelo
    proprio prev_hash (so se verificam os elos internos a janela).
    """
    esperado_por_org: dict[Any, str] = {}
    for ev in eventos:
        org_key = getattr(ev, "org_id", None)
        if org_key in esperado_por_org:
            esperado = esperado_por_org[org_key]
        elif exigir_genesis:
            esperado = GENESIS_HASH
        else:
            # 1o evento desta org na janela: confia no seu proprio prev como ancora.
            esperado = ev.prev_hash
        if ev.prev_hash != esperado:
            return False, f"prev_hash divergente em {ev.id}: esperado {esperado[:8]}, encontrado {ev.prev_hash[:8]}"
        if ev.payload_hash != hash_evento(ev):
            return False, f"payload_hash divergente em {ev.id}: evento modificado apos insercao"
        esperado_por_org[org_key] = ev.payload_hash
    return True, None
