"""Testes da feature de refresh tokens (auth.py + db/refresh_tokens.py + endpoints)."""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.db import refresh_tokens as repo
from api.services.auth import gerar_refresh_token, hash_refresh_token

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_cookies():
    # TestClient persiste cookies entre requests; limpa p/ isolar cada teste.
    client.cookies.clear()
    yield
    client.cookies.clear()


# ── Unit: geração/hash ──────────────────────────────────────────────────────

def test_gerar_refresh_token_unico_e_opaco():
    t1, t2 = gerar_refresh_token(), gerar_refresh_token()
    assert t1 != t2
    assert len(t1) >= 43           # token_urlsafe(48) ~ 64 chars
    assert "." not in t1           # não é JWT


def test_hash_refresh_token_deterministico_64hex():
    h = hash_refresh_token("abc")
    assert h == hash_refresh_token("abc")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# ── CRUD (api/db/refresh_tokens.py) com sessão mockada ──────────────────────

def _fake_db():
    db = AsyncMock()
    db.add = MagicMock()           # add é síncrono
    return db


def test_crud_criar_persiste():
    db = _fake_db()
    rt = asyncio.run(repo.criar(db, sub="s", token_hash="h",
                                expira_em=datetime.now(timezone.utc)))
    db.add.assert_called_once()
    db.commit.assert_awaited()
    db.refresh.assert_awaited()
    assert rt.sub == "s"


def test_crud_buscar_ativo_por_hash():
    db = _fake_db()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value="ROW")
    db.execute = AsyncMock(return_value=res)
    assert asyncio.run(repo.buscar_ativo_por_hash(db, "h")) == "ROW"


def test_crud_revogar():
    db = _fake_db()
    db.execute = AsyncMock()
    asyncio.run(repo.revogar(db, uuid.uuid4(), substituido_por=uuid.uuid4()))
    db.execute.assert_awaited()
    db.commit.assert_awaited()


def test_crud_revogar_por_hash_retorna_bool():
    db = _fake_db()
    res = MagicMock()
    res.rowcount = 1
    db.execute = AsyncMock(return_value=res)
    assert asyncio.run(repo.revogar_por_hash(db, "h")) is True


def test_crud_revogar_todos_do_sub_conta():
    db = _fake_db()
    res = MagicMock()
    res.rowcount = 3
    db.execute = AsyncMock(return_value=res)
    assert asyncio.run(repo.revogar_todos_do_sub(db, "s")) == 3


# ── Endpoints ───────────────────────────────────────────────────────────────

def _mock_session_cm():
    """(SessionLocal_mock, db_mock) — `async with SessionLocal() as db`."""
    db = AsyncMock()
    db.add = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    sl = MagicMock(return_value=cm)
    return sl, db


def test_refresh_sem_db_retorna_503():
    """Sem DB (default no ambiente de teste), POST /auth/refresh → 503."""
    with patch("api.routers.auth_routes._config.DB_DISPONIVEL", False):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=qualquer"})
    assert r.status_code == 503


def test_login_sem_db_nao_emite_refresh():
    from api.services.auth import hash_senha
    h = hash_senha("senha-correta-123")
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", False),
        patch.dict(os.environ, {"ORGCONC_ADMIN_EMAIL": "admin@orgconc.com",
                                "ORGCONC_ADMIN_SENHA_HASH": h}),
    ):
        r = client.post("/auth/login", json={"email": "admin@orgconc.com", "senha": "senha-correta-123"})
    assert r.status_code == 200
    j = r.json()
    assert j["access_token"]
    assert j["refresh_emitted"] is False


def test_login_com_db_emite_refresh():
    from api.services.auth import hash_senha
    h = hash_senha("senha-correta-123")
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock(return_value=MagicMock(id=uuid.uuid4()))),
        patch.dict(os.environ, {"ORGCONC_ADMIN_EMAIL": "admin@orgconc.com",
                                "ORGCONC_ADMIN_SENHA_HASH": h}),
    ):
        r = client.post("/auth/login", json={"email": "admin@orgconc.com", "senha": "senha-correta-123"})
    assert r.status_code == 200
    j = r.json()
    assert j["refresh_emitted"] is True
    assert j["refresh_ttl_days"] >= 1
    assert "orgconc_refresh" in r.headers.get("set-cookie", "")


def test_refresh_rotaciona_e_emite_novo_access():
    sl, _db = _mock_session_cm()
    fake_row = MagicMock(sub="admin@orgconc.com", role="admin", cliente_id=None, id=uuid.uuid4())
    novo_row = MagicMock(id=uuid.uuid4())
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=AsyncMock(return_value=fake_row)),
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock(return_value=novo_row)),
        patch("api.routers.auth_routes.refresh_repo.revogar", new=AsyncMock()) as mock_revogar,
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=valido"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["access_token"] and j["token_type"] == "bearer"
    mock_revogar.assert_awaited_once()  # o token antigo foi revogado (anti-replay)


def test_refresh_invalido_ou_revogado_retorna_401():
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=AsyncMock(return_value=None)),
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=revogado"})
    assert r.status_code == 401


def test_refresh_sem_cookie_retorna_401():
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", _mock_session_cm()[0]),
    ):
        r = client.post("/auth/refresh")
    assert r.status_code == 401


def test_logout_revoga_refresh():
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.revogar_por_hash", new=AsyncMock(return_value=True)) as mock_rev,
    ):
        r = client.post("/auth/logout", headers={"Cookie": "orgconc_refresh=algo"})
    assert r.status_code == 200
    mock_rev.assert_awaited_once()
