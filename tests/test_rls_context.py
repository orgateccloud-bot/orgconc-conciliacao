"""Testes do wiring de RLS por org (sem DB): extração do org_id do JWT no
middleware ASGI + listener after_begin. A prova de isolamento real (com Postgres)
está em test_rls_real_tables.py.
"""
import asyncio
import uuid
from unittest.mock import MagicMock

from api.core.bootstrap import RLSContextMiddleware, _org_id_do_scope
from api.db import rls_context
from api.services.auth import emitir_token


def _scope(headers: dict) -> dict:
    return {
        "type": "http",
        "headers": [(k.encode("latin1"), v.encode("latin1")) for k, v in headers.items()],
    }


# ── _org_id_do_scope ─────────────────────────────────────────────────────────

def test_org_id_do_bearer():
    org = str(uuid.uuid4())
    tok = emitir_token(sub="s", email="e@x.com", role="admin", org_id=org)
    assert _org_id_do_scope(_scope({"authorization": f"Bearer {tok}"})) == org


def test_org_id_do_cookie():
    org = str(uuid.uuid4())
    tok = emitir_token(sub="s", email="e@x.com", role="user", org_id=org)
    assert _org_id_do_scope(_scope({"cookie": f"foo=bar; orgconc_token={tok}"})) == org


def test_org_id_sem_token_none():
    assert _org_id_do_scope(_scope({})) is None


def test_org_id_token_invalido_none():
    assert _org_id_do_scope(_scope({"authorization": "Bearer nao.e.jwt"})) is None


def test_org_id_token_sem_org_none():
    tok = emitir_token(sub="admin@x.com", email="admin@x.com", role="admin")  # sem org_id
    assert _org_id_do_scope(_scope({"authorization": f"Bearer {tok}"})) is None


# ── Middleware seta e reseta o contexto ──────────────────────────────────────

def test_middleware_seta_e_reseta_contexto():
    org = str(uuid.uuid4())
    tok = emitir_token(sub="s", email="e@x.com", role="admin", org_id=org)
    visto = {}

    async def _inner(scope, receive, send):
        visto["org"] = rls_context.get_org_context()

    mw = RLSContextMiddleware(_inner)

    async def _noop():
        return {}

    asyncio.run(mw(_scope({"authorization": f"Bearer {tok}"}), _noop, _noop))
    assert visto["org"] == org                      # endpoint viu o org do token
    assert rls_context.get_org_context() is None     # resetado após o request


def test_middleware_ignora_nao_http():
    chamado = {}

    async def _inner(scope, receive, send):
        chamado["ok"] = True

    async def _noop():
        return {}

    asyncio.run(RLSContextMiddleware(_inner)({"type": "lifespan"}, _noop, _noop))
    assert chamado.get("ok") is True


# ── Listener after_begin ─────────────────────────────────────────────────────

def test_listener_emite_set_config_com_org():
    conn = MagicMock()
    token = rls_context.set_org_context("11111111-1111-1111-1111-111111111111")
    try:
        rls_context._set_org_no_begin(session=None, transaction=None, connection=conn)
    finally:
        rls_context.reset_org_context(token)
    conn.execute.assert_called_once()
    # o parâmetro o= deve ser o org corrente
    args, kwargs = conn.execute.call_args
    assert args[1] == {"o": "11111111-1111-1111-1111-111111111111"}


def test_listener_noop_sem_org():
    conn = MagicMock()
    token = rls_context.set_org_context(None)
    try:
        rls_context._set_org_no_begin(session=None, transaction=None, connection=conn)
    finally:
        rls_context.reset_org_context(token)
    conn.execute.assert_not_called()
