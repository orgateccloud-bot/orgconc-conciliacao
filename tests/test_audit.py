"""Testes do servico de auditoria com hash chain."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("ORGCONC_DATA_DIR", str(Path(__file__).resolve().parent / "_data_test"))
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")


def test_calcular_hash_deterministico():
    from api.services.audit import calcular_hash
    h1 = calcular_hash({"a": 1, "b": 2})
    h2 = calcular_hash({"b": 2, "a": 1})  # ordem diferente das chaves
    assert h1 == h2
    assert len(h1) == 64


def test_calcular_hash_payload_vazio():
    from api.services.audit import calcular_hash
    h = calcular_hash(None)
    assert len(h) == 64
    assert h == calcular_hash({})  # None equivalente a dict vazio


def test_calcular_hash_payloads_diferentes_geram_hashes_diferentes():
    from api.services.audit import calcular_hash
    assert calcular_hash({"x": 1}) != calcular_hash({"x": 2})


def test_genesis_hash_64_zeros():
    from api.services.audit import GENESIS_HASH
    assert GENESIS_HASH == "0" * 64


def _mk_evento(payload, prev, *, _id="e", org_id=None, action="test.action",
               actor_sub=None, actor_email=None, ts=None,
               resource_type=None, resource_id=None):
    """Constroi um stub de AuditEvent com payload_hash coerente (hash do evento)."""
    from datetime import datetime, timezone
    from api.services.audit import calcular_hash_evento

    ts = ts or datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)

    class _Ev:
        pass

    ev = _Ev()
    ev.id = _id
    ev.org_id = org_id
    ev.action = action
    ev.resource_type = resource_type
    ev.resource_id = resource_id
    ev.actor_sub = actor_sub
    ev.actor_email = actor_email
    ev.ts = ts
    ev.payload = payload
    ev.prev_hash = prev
    ev.payload_hash = calcular_hash_evento(
        action=action, resource_type=resource_type, resource_id=resource_id,
        actor_sub=actor_sub, actor_email=actor_email, ts=ts, org_id=org_id,
        payload=payload, prev_hash=prev,
    )
    return ev


def test_verificar_cadeia_integra():
    from api.services.audit import verificar_cadeia, GENESIS_HASH

    e1 = _mk_evento({"step": 1}, GENESIS_HASH, _id="e1")
    e2 = _mk_evento({"step": 2}, e1.payload_hash, _id="e2")
    e3 = _mk_evento({"step": 3}, e2.payload_hash, _id="e3")

    ok, motivo = verificar_cadeia([e1, e2, e3])
    assert ok
    assert motivo is None


def test_verificar_cadeia_por_org_independente():
    """Cada org encadeia a partir do GENESIS — interleave de orgs nao quebra."""
    from api.services.audit import verificar_cadeia, GENESIS_HASH

    a1 = _mk_evento({"a": 1}, GENESIS_HASH, _id="a1", org_id="org-A")
    b1 = _mk_evento({"b": 1}, GENESIS_HASH, _id="b1", org_id="org-B")
    a2 = _mk_evento({"a": 2}, a1.payload_hash, _id="a2", org_id="org-A")
    b2 = _mk_evento({"b": 2}, b1.payload_hash, _id="b2", org_id="org-B")

    ok, motivo = verificar_cadeia([a1, b1, a2, b2])
    assert ok, motivo


def test_verificar_cadeia_quebrada_por_prev_hash():
    from api.services.audit import verificar_cadeia, GENESIS_HASH

    e1 = _mk_evento({"a": 1}, GENESIS_HASH, _id="e1")
    e2 = _mk_evento({"a": 2}, "deadbeef" * 8, _id="e2")  # prev_hash incorreto
    ok, motivo = verificar_cadeia([e1, e2])
    assert not ok
    assert "prev_hash" in motivo


def test_verificar_cadeia_quebrada_por_payload_modificado():
    from api.services.audit import verificar_cadeia, GENESIS_HASH

    e1 = _mk_evento({"original": True}, GENESIS_HASH, _id="e1")
    # Payload alterado apos insercao — hash do evento nao bate mais.
    e1.payload = {"original": True, "tampered": True}
    ok, motivo = verificar_cadeia([e1])
    assert not ok
    assert "payload_hash" in motivo


def test_verificar_cadeia_quebrada_por_metadado_modificado():
    """Adulterar action/actor/ts (nao so o payload) quebra a cadeia (#2)."""
    from api.services.audit import verificar_cadeia, GENESIS_HASH

    e1 = _mk_evento({"x": 1}, GENESIS_HASH, _id="e1", action="login.success")
    e1.action = "login.failure"  # metadado adulterado, payload_hash inalterado
    ok, motivo = verificar_cadeia([e1])
    assert not ok
    assert "payload_hash" in motivo


def _db_com_ultimo_evento(ultimo):
    """Mock de AsyncSession cujo SELECT(ultimo hash) devolve `ultimo` (event|None)."""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = ultimo
    db.execute = AsyncMock(return_value=result)
    return db


def test_registrar_audit_genesis():
    """Primeiro evento usa GENESIS_HASH como prev_hash."""
    from api.services.audit import registrar_audit, GENESIS_HASH

    db = _db_com_ultimo_evento(None)
    ev = asyncio.run(registrar_audit(db, action="test.action", payload={"x": 1}))
    assert ev.prev_hash == GENESIS_HASH
    assert ev.action == "test.action"
    assert len(ev.payload_hash) == 64
    db.add.assert_called_once()


def test_registrar_audit_segundo_evento_encadeia():
    """Segundo evento aponta para o payload_hash do evento anterior."""
    from api.services.audit import registrar_audit

    anterior = MagicMock()
    anterior.payload_hash = "ab" * 32
    db = _db_com_ultimo_evento(anterior)

    ev = asyncio.run(registrar_audit(db, action="test.next", payload={"segundo": True}))
    assert ev.prev_hash == "ab" * 32


def test_registrar_audit_com_actor_propaga_org():
    """actor_email/sub/org_id vem do TokenPayload (#3)."""
    from api.services.audit import registrar_audit
    from api.services.auth import TokenPayload

    db = _db_com_ultimo_evento(None)
    actor = TokenPayload(sub="user-1", email="a@b.com", role="admin", org_id="org-XYZ")
    ev = asyncio.run(registrar_audit(db, action="login.success", payload={"ok": True}, actor=actor))
    assert ev.actor_email == "a@b.com"
    assert ev.actor_sub == "user-1"
    assert ev.org_id == "org-XYZ"


def test_registrar_audit_hash_cobre_metadados():
    """payload_hash do evento depende da action (#2): mesma payload, action diferente → hash diferente."""
    from api.services.audit import registrar_audit

    db1 = _db_com_ultimo_evento(None)
    db2 = _db_com_ultimo_evento(None)
    ev_a = asyncio.run(registrar_audit(db1, action="acao.A", payload={"x": 1}))
    ev_b = asyncio.run(registrar_audit(db2, action="acao.B", payload={"x": 1}))
    assert ev_a.payload_hash != ev_b.payload_hash
