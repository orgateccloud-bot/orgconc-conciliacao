"""test_rls_isolation.py — PROVA que a RLS por organização está ativa.

Escrever a migration ≠ provar que funciona. Este teste roda contra um Postgres
REAL conectando com o role `app_orgconc` (NOBYPASSRLS) e cobre os 4 modos de
falha reais:
  1. leitura cruzada   — org A não vê linha de B
  2. sem tenant setado — falha FECHADA: zero linhas (não "tudo")
  3. escrita cruzada   — A não grava como B (WITH CHECK)
  4. update/delete cruzado — A não altera nem apaga linha de B

Tenant = org_id (a firma contábil). Aplica db/rls/contraparte_org_isolation.sql.
Pulado quando não há DATABASE_URL (Postgres real) — ex.: ambiente sem banco.
"""
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_RAW = os.environ.get("DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not _RAW, reason="RLS exige DATABASE_URL (Postgres real)")

ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"
_APP_PW = "rls_poc_app_pw"
_SQL = Path(__file__).resolve().parent.parent / "db" / "rls" / "contraparte_org_isolation.sql"


def _url(driver: str, user: str | None = None, pw: str | None = None) -> str:
    p = urlsplit(_RAW.replace("postgresql+asyncpg://", "postgresql://", 1))
    host = p.hostname or "localhost"
    port = f":{p.port}" if p.port else ""
    u = user or p.username or "postgres"
    w = pw if pw is not None else (p.password or "")
    return urlunsplit((driver, f"{u}:{w}@{host}{port}", p.path or "/postgres", "", ""))


@pytest_asyncio.fixture
async def app_session_maker():
    import asyncpg

    # Setup como OWNER: aplica o SQL de RLS, fixa a senha do app role, limpa a tabela.
    conn = await asyncpg.connect(_url("postgresql"))
    try:
        await conn.execute(_SQL.read_text(encoding="utf-8"))
        await conn.execute(f"ALTER ROLE app_orgconc PASSWORD '{_APP_PW}'")
        await conn.execute("TRUNCATE public.contraparte")
    finally:
        await conn.close()

    # Sessões como app_orgconc (NOBYPASSRLS → a RLS se aplica de verdade).
    engine = create_async_engine(_url("postgresql+asyncpg", "app_orgconc", _APP_PW))
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _criar(session, org_id: str, nome: str) -> None:
    await session.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": org_id})
    await session.execute(
        text("INSERT INTO public.contraparte (org_id, nome_real) VALUES (:o, :n)"),
        {"o": org_id, "n": nome},
    )


@pytest.mark.asyncio
async def test_org_nao_le_dado_de_outro(app_session_maker):
    """Org A insere; org B não enxerga."""
    async with app_session_maker() as s, s.begin():
        await _criar(s, ORG_A, "Fornecedor Alfa")
        await _criar(s, ORG_B, "Fornecedor Beta")
    async with app_session_maker() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": ORG_A})
        rows = (await s.execute(text("SELECT nome_real FROM public.contraparte"))).scalars().all()
    assert "Fornecedor Alfa" in rows
    assert "Fornecedor Beta" not in rows, "VAZAMENTO: A enxergou dado de B"


@pytest.mark.asyncio
async def test_sem_org_zero_linhas(app_session_maker):
    """Falha FECHADA: sem app.org_id setado, não devolve nada — não tudo."""
    async with app_session_maker() as s, s.begin():
        await _criar(s, ORG_A, "Existe")
    async with app_session_maker() as s, s.begin():
        rows = (await s.execute(text("SELECT 1 FROM public.contraparte"))).all()
    assert rows == [], "FALHA ABERTA: sem tenant a query devolveu linhas"


@pytest.mark.asyncio
async def test_with_check_bloqueia_escrita_cruzada(app_session_maker):
    """Org A não consegue inserir linha marcada como B (WITH CHECK)."""
    # pytest.raises envolve o begin(): a violação propaga e a transação faz
    # rollback no exit do context manager (sem commit em transação abortada).
    with pytest.raises(Exception):
        async with app_session_maker() as s, s.begin():
            await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": ORG_A})
            await s.execute(
                text("INSERT INTO public.contraparte (org_id, nome_real) VALUES (:o, 'Intruso')"),
                {"o": ORG_B},
            )


@pytest.mark.asyncio
async def test_update_delete_cruzado_nao_afeta_outro(app_session_maker):
    """A tenta apagar tudo; linha de B sobrevive (A nem a enxerga)."""
    async with app_session_maker() as s, s.begin():
        await _criar(s, ORG_B, "Sobrevivente")
    async with app_session_maker() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": ORG_A})
        await s.execute(text("DELETE FROM public.contraparte"))  # só apaga de A
    async with app_session_maker() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": ORG_B})
        rows = (await s.execute(text("SELECT nome_real FROM public.contraparte"))).scalars().all()
    assert "Sobrevivente" in rows, "A apagou dado de B"
