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
from api.services import auth as auth_svc
from api.services.auth import (
    TokenPayload,
    decodificar_token,
    emitir_token,
    escopo_cliente_listagem,
    gerar_refresh_token,
    hash_refresh_token,
    jti_revogado,
    revogar_jti,
)
from fastapi import HTTPException


class _FakeRedis:
    """Redis em memória (subset usado pela denylist): setex + exists."""

    def __init__(self):
        self.store = {}

    def setex(self, key, ttl, val):
        self.store[key] = (val, ttl)

    def exists(self, key):
        return 1 if key in self.store else 0

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

def _fake_db(*, ativos_ids=None):
    """AsyncSession mockada.

    `db.execute(...)` retorna um Result SÍNCRONO (como o SQLAlchemy real):
    `scalars()` e `scalars().all()` não são corrotinas. `ativos_ids` é a lista
    de ids que o SELECT de sessões ativas (#25) deve devolver (default: vazia).
    """
    db = AsyncMock()
    db.add = MagicMock()           # add é síncrono
    res = MagicMock()              # Result é síncrono
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=list(ativos_ids or []))
    res.scalars = MagicMock(return_value=scalars)
    res.rowcount = len(ativos_ids or [])
    db.execute = AsyncMock(return_value=res)
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
        # login agora consulta usuarios primeiro; sem usuário casando → admin por env.
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_email", new=AsyncMock(return_value=None)),
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
        patch("api.routers.auth_routes.refresh_repo.buscar_por_hash", new=AsyncMock(return_value=None)),
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=revogado"})
    assert r.status_code == 401


def test_refresh_reuse_detection_revoga_familia():
    """Token JÁ ROTACIONADO reapresentado fora da janela de graça → revoga
    todas as sessões do sub (RFC 6819 reuse-detection) e responde 401."""
    from datetime import datetime, timedelta, timezone

    sl, _db = _mock_session_cm()
    antigo = MagicMock(
        id=uuid.uuid4(),
        sub="vitima@orgconc.com",
        role="user",
        revogado_em=datetime.now(timezone.utc) - timedelta(seconds=60),
        substituido_por=uuid.uuid4(),
    )
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=AsyncMock(return_value=None)),
        patch("api.routers.auth_routes.refresh_repo.buscar_por_hash", new=AsyncMock(return_value=antigo)),
        patch("api.routers.auth_routes.refresh_repo.revogar_todos_do_sub", new=AsyncMock(return_value=3)) as mock_rev,
        patch("api.routers.auth_routes.gravar_audit_independente", new=AsyncMock()) as mock_audit,
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=roubado"})
    assert r.status_code == 401
    mock_rev.assert_awaited_once()
    mock_audit.assert_awaited_once()


def test_refresh_corrida_benigna_na_janela_de_graca_nao_revoga_familia():
    """Reapresentação DENTRO da janela de 10s (tabs paralelas) → 401 simples,
    sem revogar a família."""
    from datetime import datetime, timedelta, timezone

    sl, _db = _mock_session_cm()
    antigo = MagicMock(
        id=uuid.uuid4(),
        sub="user@orgconc.com",
        role="user",
        revogado_em=datetime.now(timezone.utc) - timedelta(seconds=2),
        substituido_por=uuid.uuid4(),
    )
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=AsyncMock(return_value=None)),
        patch("api.routers.auth_routes.refresh_repo.buscar_por_hash", new=AsyncMock(return_value=antigo)),
        patch("api.routers.auth_routes.refresh_repo.revogar_todos_do_sub", new=AsyncMock()) as mock_rev,
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=corrida"})
    assert r.status_code == 401
    mock_rev.assert_not_awaited()


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


def test_logout_sem_refresh_e_idempotente():
    # Logout sem cookie de refresh: não toca o banco, ainda assim 200 (idempotente).
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", _mock_session_cm()[0]),
        patch("api.routers.auth_routes.refresh_repo.revogar_por_hash", new=AsyncMock()) as mock_rev,
    ):
        r = client.post("/auth/logout")
    assert r.status_code == 200
    mock_rev.assert_not_awaited()


def test_logout_all_revoga_todos_do_sub():
    # logout-all exige auth (current_user) e revoga TODOS os refresh do usuário.
    sl, _db = _mock_session_cm()
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch(
            "api.routers.auth_routes.refresh_repo.revogar_todos_do_sub",
            new=AsyncMock(return_value=3),
        ) as mock_rev_all,
    ):
        r = client.post("/auth/logout-all")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["revogados"] == 3
    mock_rev_all.assert_awaited_once()


# ── #22 rotação atômica (FOR UPDATE) ─────────────────────────────────────────

def test_buscar_ativo_for_update_aplica_lock():
    """for_update=True adiciona FOR UPDATE ao SELECT (lock de linha)."""
    db = _fake_db()
    captured = {}

    async def _exec(q):
        captured["sql"] = str(q.compile(compile_kwargs={"literal_binds": False}))
        res = MagicMock()
        res.scalar_one_or_none = MagicMock(return_value="ROW")
        return res

    db.execute = AsyncMock(side_effect=_exec)
    asyncio.run(repo.buscar_ativo_por_hash(db, "h", for_update=True))
    assert "FOR UPDATE" in captured["sql"].upper()


def test_buscar_ativo_sem_for_update_nao_aplica_lock():
    db = _fake_db()
    captured = {}

    async def _exec(q):
        captured["sql"] = str(q.compile(compile_kwargs={"literal_binds": False}))
        res = MagicMock()
        res.scalar_one_or_none = MagicMock(return_value="ROW")
        return res

    db.execute = AsyncMock(side_effect=_exec)
    asyncio.run(repo.buscar_ativo_por_hash(db, "h", for_update=False))
    assert "FOR UPDATE" not in captured["sql"].upper()


def test_refresh_concorrente_segundo_request_falha_401():
    """Rotação concorrente: o 2º request (token já consumido) recebe None do
    buscar_ativo (FOR UPDATE serializou) → reuse-detection → 401, sem emitir
    um 2º access válido."""
    sl, _db = _mock_session_cm()
    # Simula a corrida: a 1ª chamada acha o token; a 2ª (após o 1º revogar) não.
    busca = AsyncMock(side_effect=[None])  # 2º request: token já consumido
    # A base tem reuse-detection: ao não achar ativo, busca o token (revogado)
    # por hash. Aqui mockamos como ausente → 401 simples, sem revogar família.
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=busca),
        patch("api.routers.auth_routes.refresh_repo.buscar_por_hash", new=AsyncMock(return_value=None)),
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock()) as mock_criar,
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=consumido"})
    assert r.status_code == 401
    mock_criar.assert_not_awaited()  # 2º request NÃO emite novo token


def test_refresh_usa_for_update():
    """O endpoint de refresh chama buscar_ativo com for_update=True."""
    sl, _db = _mock_session_cm()
    fake_row = MagicMock(sub="admin@orgconc.com", role="admin", cliente_id=None, id=uuid.uuid4())
    busca = AsyncMock(return_value=fake_row)
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=busca),
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock(return_value=MagicMock(id=uuid.uuid4()))),
        patch("api.routers.auth_routes.refresh_repo.revogar", new=AsyncMock()),
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=valido"})
    assert r.status_code == 200, r.text
    # for_update foi passado como True
    _, kwargs = busca.call_args
    assert kwargs.get("for_update") is True


# ── #25 limite de sessões ativas por sub ─────────────────────────────────────

def test_limite_sessoes_revoga_os_mais_antigos():
    """Ao exceder o teto, revoga os N mais antigos (ordem por emitido_em.asc)."""
    # SELECT já retorna em ordem crescente de emitido_em (mais antigo primeiro).
    ids = [uuid.uuid4() for _ in range(5)]
    db = _fake_db()
    selres = MagicMock()
    selres.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=list(ids))))
    updres = MagicMock()
    updres.rowcount = 3
    db.execute = AsyncMock(side_effect=[selres, updres])

    n = asyncio.run(repo._revogar_excedentes_do_sub(db, "s", manter=2))
    assert n == 3  # 5 ativos, manter 2 → revoga 3
    assert db.execute.await_count == 2  # SELECT + UPDATE
    # o UPDATE alveja exatamente os 3 mais antigos (ids[:3]).
    update_stmt = db.execute.await_args_list[1].args[0]
    sql = str(update_stmt.compile(compile_kwargs={"literal_binds": True}))
    # o UUID é serializado sem hífens na SQL compilada.
    sql_hex = sql.replace("-", "")
    assert sql.upper().startswith("UPDATE")
    for antigo in ids[:3]:
        assert antigo.hex in sql_hex
    # os 2 mais recentes NÃO entram no UPDATE.
    for recente in ids[3:]:
        assert recente.hex not in sql_hex


def test_limite_sessoes_nao_revoga_dentro_do_teto():
    ids = [uuid.uuid4(), uuid.uuid4()]
    db = _fake_db()
    selres = MagicMock()
    selres.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=list(ids))))
    db.execute = AsyncMock(return_value=selres)
    n = asyncio.run(repo._revogar_excedentes_do_sub(db, "s", manter=10))
    assert n == 0
    # só o SELECT; nenhum UPDATE.
    assert db.execute.await_count == 1


def test_criar_aplica_limite_sessoes():
    """criar() invoca o controle de limite (flush + select de ativos)."""
    db = _fake_db(ativos_ids=[])  # sem excedentes
    asyncio.run(repo.criar(db, sub="s", token_hash="h",
                           expira_em=datetime.now(timezone.utc)))
    db.flush.assert_awaited()       # flush p/ materializar o INSERT
    db.execute.assert_awaited()     # SELECT de sessões ativas (#25)
    db.commit.assert_awaited()


# ── #24 admin-por-env desativado não reganha superadmin no refresh ───────────

def test_refresh_admin_env_ativo_reganha_superadmin():
    sl, _db = _mock_session_cm()
    fake_row = MagicMock(sub="admin@orgconc.com", role="admin", cliente_id=None, id=uuid.uuid4())
    from api.services.auth import hash_senha, decodificar_token
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=AsyncMock(return_value=fake_row)),
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock(return_value=MagicMock(id=uuid.uuid4()))),
        patch("api.routers.auth_routes.refresh_repo.revogar", new=AsyncMock()),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_id", new=AsyncMock(return_value=None)),
        patch.dict(os.environ, {"ORGCONC_ADMIN_EMAIL": "admin@orgconc.com",
                                "ORGCONC_ADMIN_SENHA_HASH": hash_senha("x")}),
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=valido"})
    assert r.status_code == 200, r.text
    claims = decodificar_token(r.json()["access_token"])
    assert claims.superadmin is True


def test_refresh_admin_env_desativado_nao_reganha_superadmin():
    """#24 — se o admin-por-env foi desativado (env removido), o refresh NÃO
    reconcede superadmin, mesmo com sub == antigo ORGCONC_ADMIN_EMAIL."""
    sl, _db = _mock_session_cm()
    fake_row = MagicMock(sub="admin@orgconc.com", role="admin", cliente_id=None, id=uuid.uuid4())
    from api.services.auth import decodificar_token
    env_sem_admin = {k: v for k, v in os.environ.items()
                     if k not in ("ORGCONC_ADMIN_EMAIL", "ORGCONC_ADMIN_SENHA_HASH")}
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", True),
        patch("api.routers.auth_routes._config.SessionLocal", sl),
        patch("api.routers.auth_routes.refresh_repo.buscar_ativo_por_hash", new=AsyncMock(return_value=fake_row)),
        patch("api.routers.auth_routes.refresh_repo.criar", new=AsyncMock(return_value=MagicMock(id=uuid.uuid4()))),
        patch("api.routers.auth_routes.refresh_repo.revogar", new=AsyncMock()),
        patch("api.routers.auth_routes.usuarios_repo.buscar_por_id", new=AsyncMock(return_value=None)),
        patch.dict(os.environ, env_sem_admin, clear=True),
    ):
        r = client.post("/auth/refresh", headers={"Cookie": "orgconc_refresh=valido"})
    assert r.status_code == 200, r.text
    claims = decodificar_token(r.json()["access_token"])
    assert claims.superadmin is False


# ── #9 denylist de access token por jti ──────────────────────────────────────

@pytest.fixture
def _fake_denylist():
    """Substitui o cliente Redis da denylist por um fake em memória."""
    fake = _FakeRedis()
    with patch("api.services.auth._get_denylist_redis", return_value=fake):
        yield fake


def test_token_revogado_falha_em_decodificar(_fake_denylist):
    tok = emitir_token(sub="u1", role="user")
    claims = decodificar_token(tok)            # válido antes de revogar
    assert claims.sub == "u1"
    assert revogar_jti(claims.jti, claims.exp) is True
    assert jti_revogado(claims.jti) is True
    with pytest.raises(HTTPException) as exc:
        decodificar_token(tok)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token revogado"


def test_token_nao_revogado_decodifica(_fake_denylist):
    tok = emitir_token(sub="u2", role="user")
    claims = decodificar_token(tok)
    assert claims.sub == "u2"
    assert jti_revogado(claims.jti) is False


def test_denylist_sem_redis_degrada_sem_quebrar():
    """Sem Redis (REDIS_URL ausente): revogar_jti retorna False e jti_revogado
    retorna False — decodificar continua funcionando (degrada, não quebra)."""
    with patch("api.services.auth._get_denylist_redis", return_value=None):
        tok = emitir_token(sub="u3", role="user")
        claims = decodificar_token(tok)
        assert revogar_jti(claims.jti, claims.exp) is False
        assert jti_revogado(claims.jti) is False
        # mesmo "revogado", sem store o token continua válido (fail-open)
        assert decodificar_token(tok).sub == "u3"


def test_revogar_jti_token_expirado_nao_grava(_fake_denylist):
    """exp no passado → TTL <= 0 → não grava (já barrado pela validação de exp)."""
    passado = int(datetime.now(timezone.utc).timestamp()) - 10
    assert revogar_jti("jti-velho", passado) is False
    assert _fake_denylist.exists("revoked:jti-velho") == 0


def test_logout_revoga_jti_do_access(_fake_denylist):
    """#9 — logout coloca o jti do access atual na denylist."""
    tok = emitir_token(sub="u4", role="user")
    claims = decodificar_token(tok)
    with (
        patch("api.routers.auth_routes._config.DB_DISPONIVEL", False),
    ):
        r = client.post("/auth/logout", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert jti_revogado(claims.jti) is True


# ── #23 escopo de cliente em listagem (multi-org) ────────────────────────────

def test_escopo_admin_pode_qualquer_cliente():
    admin = TokenPayload(sub="a", role="admin", org_id="org-1")
    assert escopo_cliente_listagem(admin, "cli-de-outra-org") == "cli-de-outra-org"
    assert escopo_cliente_listagem(admin, None) is None


def test_escopo_user_com_cliente_id_so_o_proprio():
    user = TokenPayload(sub="u", role="user", org_id="org-1", cliente_id="cli-1")
    assert escopo_cliente_listagem(user, "cli-1") == "cli-1"
    assert escopo_cliente_listagem(user, None) == "cli-1"  # default = o próprio
    with pytest.raises(HTTPException) as exc:
        escopo_cliente_listagem(user, "cli-2")  # cliente de outra org
    assert exc.value.status_code == 403


def test_escopo_user_multiorg_sem_cliente_nao_passa_arbitrario():
    """#23 — user multi-org (sem cliente_id no token) NÃO pode escopar a um
    cliente_id arbitrário (era o furo de vazamento cross-org)."""
    user = TokenPayload(sub="u", role="user", org_id="org-1", cliente_id=None)
    assert escopo_cliente_listagem(user, None) is None
    with pytest.raises(HTTPException) as exc:
        escopo_cliente_listagem(user, "cli-arbitrario")
    assert exc.value.status_code == 403
