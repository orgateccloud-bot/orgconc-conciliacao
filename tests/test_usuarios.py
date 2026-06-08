"""Testes do auth multi-org (usuarios): repo + login/refresh + endpoints.

Seguem o padrão de test_refresh_tokens.py: sessão e repo mockados (async),
sem Postgres real. Cobrem a lógica nova de identidade (token carrega org_id),
o fallback do admin por env e a autorização dos endpoints de gestão.
"""
import asyncio
import os
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.db import usuarios as repo
from api.services.auth import decodificar_token, emitir_token, hash_senha

client = TestClient(app)

_SENHA = "senha-correta-123"
_HASH = hash_senha(_SENHA)


@pytest.fixture(autouse=True)
def _clear_cookies():
    client.cookies.clear()
    yield
    client.cookies.clear()


def _fake_user(role="auditor", ativo=True):
    return types.SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        email="user@empresa.com",
        senha_hash=_HASH,
        nome="Fulano",
        role=role,
        ativo=ativo,
    )


def _mock_session_cm():
    """(SessionLocal_mock, db_mock) — `async with SessionLocal() as db`."""
    db = AsyncMock()
    db.add = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    sl = MagicMock(return_value=cm)
    return sl, db


# ── Repo (api/db/usuarios.py) ────────────────────────────────────────────────

def test_criar_normaliza_email_e_persiste():
    db = AsyncMock()
    db.add = MagicMock()
    u = asyncio.run(repo.criar(db, email="  User@Empresa.COM ", senha_hash="h",
                               org_id=uuid.uuid4(), role="user"))
    db.add.assert_called_once()
    db.commit.assert_awaited()
    assert u.email == "user@empresa.com"  # normalizado lowercase + strip


def test_buscar_por_id_uuid_invalido_nao_toca_db():
    db = AsyncMock()
    res = asyncio.run(repo.buscar_por_id(db, "nao-e-uuid"))
    assert res is None
    db.execute.assert_not_called()  # curto-circuito antes da query


def test_buscar_por_email_retorna_scalar():
    db = AsyncMock()
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value="ROW")
    db.execute = AsyncMock(return_value=r)
    assert asyncio.run(repo.buscar_por_email(db, "a@b.com")) == "ROW"


# ── JWT carrega org_id (api/services/auth.py) ────────────────────────────────

def test_token_roundtrip_org_id():
    org = str(uuid.uuid4())
    tok = emitir_token(sub="s", email="e@x.com", role="auditor", org_id=org)
    claims = decodificar_token(tok)
    assert claims.org_id == org and claims.role == "auditor"


# ── Login multi-org ──────────────────────────────────────────────────────────

def test_login_usuario_db_emite_token_com_org_id():
    user = _fake_user(role="auditor")
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_email", new=AsyncMock(return_value=user)),
        patch("api.routers.auth_routes.usuarios_repo.registrar_login", new=AsyncMock()) as mock_reg,
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock(return_value=MagicMock(id=uuid.uuid4()))),
    ):
        r = client.post("/auth/login", json={"email": "user@empresa.com", "senha": _SENHA})
    assert r.status_code == 200, r.text
    claims = decodificar_token(r.json()["access_token"])
    assert claims.org_id == str(user.org_id)
    assert claims.role == "auditor"
    assert claims.sub == str(user.id)
    assert claims.superadmin is False  # usuário do DB nunca é superadmin
    mock_reg.assert_awaited_once()  # ultimo_login_em carimbado


def test_login_usuario_db_senha_errada_401():
    user = _fake_user()
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_email", new=AsyncMock(return_value=user)),
    ):
        r = client.post("/auth/login", json={"email": "user@empresa.com", "senha": "errada"})
    assert r.status_code == 401


def test_login_usuario_inexistente_401():
    """buscar_por_email devolve None (inclui usuário inativo) e email != admin."""
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_email", new=AsyncMock(return_value=None)),
        patch.dict(os.environ, {"ORGCONC_ADMIN_EMAIL": "admin@orgconc.com", "ORGCONC_ADMIN_SENHA_HASH": _HASH}),
    ):
        r = client.post("/auth/login", json={"email": "ninguem@empresa.com", "senha": _SENHA})
    assert r.status_code == 401


def test_login_fallback_admin_env_quando_db_sem_usuario():
    """DB ligado mas sem usuário casando → cai no admin por env (sem org)."""
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_email", new=AsyncMock(return_value=None)),
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock(return_value=MagicMock(id=uuid.uuid4()))),
        patch.dict(os.environ, {"ORGCONC_ADMIN_EMAIL": "admin@orgconc.com", "ORGCONC_ADMIN_SENHA_HASH": _HASH}),
    ):
        r = client.post("/auth/login", json={"email": "admin@orgconc.com", "senha": _SENHA})
    assert r.status_code == 200, r.text
    claims = decodificar_token(r.json()["access_token"])
    assert claims.role == "admin" and claims.org_id is None
    assert claims.superadmin is True  # admin por env é superadmin (leitura cross-org)


# ── Refresh re-deriva org/role do usuário ────────────────────────────────────

def test_refresh_usuario_db_rederiva_org_id():
    user = _fake_user(role="user")
    fake_row = MagicMock(sub=str(user.id), role="user", cliente_id=None, id=uuid.uuid4())
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=AsyncMock(return_value=fake_row)),
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock(return_value=MagicMock(id=uuid.uuid4()))),
        patch("api.routers.auth_routes.refresh_repo.revogar", new=AsyncMock()),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_id", new=AsyncMock(return_value=user)),
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=valido"})
    assert r.status_code == 200, r.text
    claims = decodificar_token(r.json()["access_token"])
    assert claims.org_id == str(user.org_id) and claims.role == "user"


def test_refresh_usuario_desativado_barra_401():
    """sub é UUID mas o usuário não está mais ativo (buscar_por_id → None)."""
    sub_uuid = str(uuid.uuid4())
    fake_row = MagicMock(sub=sub_uuid, role="user", cliente_id=None, id=uuid.uuid4())
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=AsyncMock(return_value=fake_row)),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_id", new=AsyncMock(return_value=None)),
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=valido"})
    assert r.status_code == 401


def test_refresh_sessao_legada_email_preserva():
    """sub = email (admin por env): buscar_por_id → None mas não barra (não é uuid)."""
    fake_row = MagicMock(sub="admin@orgconc.com", role="admin", cliente_id=None, id=uuid.uuid4())
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=AsyncMock(return_value=fake_row)),
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock(return_value=MagicMock(id=uuid.uuid4()))),
        patch("api.routers.auth_routes.refresh_repo.revogar", new=AsyncMock()),
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=valido"})
    assert r.status_code == 200, r.text
    claims = decodificar_token(r.json()["access_token"])
    assert claims.role == "admin" and claims.org_id is None


# ── Endpoints de gestão: autorização ─────────────────────────────────────────

def _bearer(role: str) -> dict:
    return {"Authorization": f"Bearer {emitir_token(sub='x', email='x@x.com', role=role)}"}


def test_criar_org_anonimo_403():
    r = client.post("/auth/orgs", json={"nome": "ACME"})
    assert r.status_code == 403


def test_criar_org_role_user_403():
    r = client.post("/auth/orgs", json={"nome": "ACME"}, headers=_bearer("user"))
    assert r.status_code == 403


def test_criar_usuario_role_user_403():
    r = client.post("/auth/usuarios",
                    json={"email": "a@b.com", "senha": "12345678", "org_id": str(uuid.uuid4())},
                    headers=_bearer("user"))
    assert r.status_code == 403


def test_listar_usuarios_anonimo_403():
    r = client.get("/auth/usuarios", params={"org_id": str(uuid.uuid4())})
    assert r.status_code == 403


def test_criar_usuario_senha_curta_422():
    """Validação Pydantic (min_length=8) ocorre antes de tocar o banco."""
    r = client.post("/auth/usuarios",
                    json={"email": "a@b.com", "senha": "curta", "org_id": str(uuid.uuid4())},
                    headers=_bearer("admin"))
    assert r.status_code == 422


# ── Endpoints de gestão: caminho feliz (DB mockado) ──────────────────────────

def test_criar_usuario_org_inexistente_404():
    sl, db = _mock_session_cm()
    db.get = AsyncMock(return_value=None)  # org não existe
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
    ):
        r = client.post("/auth/usuarios",
                        json={"email": "a@b.com", "senha": "12345678", "org_id": str(uuid.uuid4())},
                        headers=_bearer("admin"))
    assert r.status_code == 404


def test_criar_usuario_sucesso():
    novo = types.SimpleNamespace(id=uuid.uuid4(), email="a@b.com", role="user")
    sl, db = _mock_session_cm()
    db.get = AsyncMock(return_value=MagicMock())  # org existe
    org_id = str(uuid.uuid4())
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.usuarios_repo.criar", new=AsyncMock(return_value=novo)),
    ):
        r = client.post("/auth/usuarios",
                        json={"email": "a@b.com", "senha": "12345678", "org_id": org_id, "role": "user"},
                        headers=_bearer("admin"))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["email"] == "a@b.com" and j["org_id"] == org_id and j["role"] == "user"
    assert "senha" not in j and "senha_hash" not in j


def test_criar_org_sucesso():
    sl, db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
    ):
        r = client.post("/auth/orgs", json={"nome": "ACME LTDA", "plano": "basico"},
                        headers=_bearer("admin"))
    assert r.status_code == 200, r.text
    assert r.json()["nome"] == "ACME LTDA" and r.json()["plano"] == "basico"


# ── Listar organizações (admin/service) ──────────────────────────────────────

def test_listar_orgs_anonimo_403():
    r = client.get("/auth/orgs")
    assert r.status_code == 403


def test_listar_orgs_role_user_403():
    r = client.get("/auth/orgs", headers=_bearer("user"))
    assert r.status_code == 403


def test_listar_orgs_sucesso():
    org = types.SimpleNamespace(
        id=uuid.uuid4(), nome="ACME LTDA", cnpj="12.345.678/0001-90",
        plano="pro", ativo=True, criado_em=None,
    )
    sl, db = _mock_session_cm()
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[org])))
    db.execute = AsyncMock(return_value=result)
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
    ):
        r = client.get("/auth/orgs", headers=_bearer("admin"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list) and len(body) == 1
    assert body[0]["id"] == str(org.id)
    assert body[0]["nome"] == "ACME LTDA" and body[0]["plano"] == "pro"
    assert body[0]["cnpj"] == "12.345.678/0001-90" and body[0]["ativo"] is True


# ── Troca de senha (self-service) ────────────────────────────────────────────

def _bearer_uuid(uid: str, role: str = "user") -> dict:
    return {"Authorization": f"Bearer {emitir_token(sub=uid, email='u@e.com', role=role)}"}


def test_trocar_senha_self_sucesso():
    uid = str(uuid.uuid4())
    user = types.SimpleNamespace(id=uid, senha_hash=_HASH)
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_id", new=AsyncMock(return_value=user)),
        patch("api.routers.auth_routes.usuarios_repo.atualizar_senha", new=AsyncMock(return_value=1)) as mock_upd,
        patch("api.routers.auth_routes.refresh_repo.revogar_todos_do_sub", new=AsyncMock(return_value=2)) as mock_rev,
    ):
        r = client.post("/auth/senha", json={"senha_atual": _SENHA, "senha_nova": "nova-senha-123"},
                        headers=_bearer_uuid(uid))
    assert r.status_code == 200, r.text
    mock_upd.assert_awaited_once()
    mock_rev.assert_awaited_once()  # sessões revogadas


def test_trocar_senha_self_atual_errada_401():
    uid = str(uuid.uuid4())
    user = types.SimpleNamespace(id=uid, senha_hash=_HASH)
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_id", new=AsyncMock(return_value=user)),
    ):
        r = client.post("/auth/senha", json={"senha_atual": "errada", "senha_nova": "nova-senha-123"},
                        headers=_bearer_uuid(uid))
    assert r.status_code == 401


def test_trocar_senha_env_admin_400():
    """sub = email (admin por env) → não há usuário no DB para trocar."""
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", _mock_session_cm()[0]),
    ):
        r = client.post("/auth/senha", json={"senha_atual": "x", "senha_nova": "nova-senha-123"},
                        headers=_bearer("admin"))  # sub='x' (não-uuid)
    assert r.status_code == 400


def test_trocar_senha_curta_422():
    r = client.post("/auth/senha", json={"senha_atual": "x", "senha_nova": "curta"},
                    headers=_bearer_uuid(str(uuid.uuid4())))
    assert r.status_code == 422


# ── Reset de senha (admin) ───────────────────────────────────────────────────

def test_reset_senha_admin_sucesso():
    uid = str(uuid.uuid4())
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.usuarios_repo.atualizar_senha", new=AsyncMock(return_value=1)),
        patch("api.routers.auth_routes.refresh_repo.revogar_todos_do_sub", new=AsyncMock(return_value=0)),
    ):
        r = client.post(f"/auth/usuarios/{uid}/senha", json={"senha_nova": "nova-senha-123"},
                        headers=_bearer("admin"))
    assert r.status_code == 200, r.text


def test_reset_senha_inexistente_404():
    uid = str(uuid.uuid4())
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.usuarios_repo.atualizar_senha", new=AsyncMock(return_value=0)),
    ):
        r = client.post(f"/auth/usuarios/{uid}/senha", json={"senha_nova": "nova-senha-123"},
                        headers=_bearer("admin"))
    assert r.status_code == 404


def test_reset_senha_nao_admin_403():
    r = client.post(f"/auth/usuarios/{uuid.uuid4()}/senha", json={"senha_nova": "nova-senha-123"},
                    headers=_bearer_uuid(str(uuid.uuid4()), role="user"))
    assert r.status_code == 403
