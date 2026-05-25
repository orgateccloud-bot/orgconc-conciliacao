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


def test_verificar_cadeia_integra():
    from api.services.audit import calcular_hash, verificar_cadeia, GENESIS_HASH

    class _Ev:
        def __init__(self, payload, prev):
            self.id = "e"
            self.payload = payload
            self.payload_hash = calcular_hash(payload)
            self.prev_hash = prev

    e1 = _Ev({"step": 1}, GENESIS_HASH)
    e2 = _Ev({"step": 2}, e1.payload_hash)
    e3 = _Ev({"step": 3}, e2.payload_hash)

    ok, motivo = verificar_cadeia([e1, e2, e3])
    assert ok
    assert motivo is None


def test_verificar_cadeia_quebrada_por_prev_hash():
    from api.services.audit import calcular_hash, verificar_cadeia, GENESIS_HASH

    class _Ev:
        def __init__(self, payload, prev, _id="x"):
            self.id = _id
            self.payload = payload
            self.payload_hash = calcular_hash(payload)
            self.prev_hash = prev

    e1 = _Ev({"a": 1}, GENESIS_HASH, "e1")
    e2 = _Ev({"a": 2}, "deadbeef" * 8, "e2")  # prev_hash incorreto
    ok, motivo = verificar_cadeia([e1, e2])
    assert not ok
    assert "prev_hash" in motivo


def test_verificar_cadeia_quebrada_por_payload_modificado():
    from api.services.audit import calcular_hash, verificar_cadeia, GENESIS_HASH

    class _Ev:
        def __init__(self, payload, payload_hash, prev, _id="x"):
            self.id = _id
            self.payload = payload
            self.payload_hash = payload_hash
            self.prev_hash = prev

    h1 = calcular_hash({"original": True})
    # Payload alterado apos insercao — hash nao bate mais
    e1 = _Ev({"original": True, "tampered": True}, h1, GENESIS_HASH, "e1")
    ok, motivo = verificar_cadeia([e1])
    assert not ok
    assert "payload_hash" in motivo


def test_registrar_audit_genesis():
    """Primeiro evento usa GENESIS_HASH como prev_hash."""
    from api.services.audit import registrar_audit, GENESIS_HASH

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    ev = asyncio.run(registrar_audit(db, action="test.action", payload={"x": 1}))
    assert ev.prev_hash == GENESIS_HASH
    assert ev.action == "test.action"
    assert len(ev.payload_hash) == 64
    db.add.assert_called_once()


def test_registrar_audit_segundo_evento_encadeia():
    """Segundo evento aponta para hash do anterior."""
    from api.services.audit import registrar_audit, calcular_hash

    hash_anterior = calcular_hash({"primeiro": True})
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = hash_anterior
    db.execute = AsyncMock(return_value=result)

    ev = asyncio.run(registrar_audit(db, action="test.next", payload={"segundo": True}))
    assert ev.prev_hash == hash_anterior


def test_registrar_audit_com_actor():
    from api.services.audit import registrar_audit
    from api.services.auth import TokenPayload

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    actor = TokenPayload(sub="user-1", email="a@b.com", role="admin")
    ev = asyncio.run(registrar_audit(db, action="login.success", payload={"ok": True}, actor=actor))
    assert ev.actor_email == "a@b.com"
    assert ev.actor_sub == "user-1"
