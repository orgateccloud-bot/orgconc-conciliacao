"""test_rls_real_tables.py — PROVA a RLS por org numa tabela REAL do app.

Estende test_rls_isolation.py (tabela de demonstração `contraparte`) para uma
tabela do schema real — `clientes` —, criada via Base.metadata.create_all e
isolada por db/rls/org_isolation.sql. Conecta como `app_orgconc` (NOBYPASSRLS),
então a RLS se aplica de verdade. Cobre os 3 modos essenciais:
  1. leitura cruzada — org A não vê cliente de B
  2. sem tenant      — falha FECHADA: zero linhas
  3. escrita cruzada — A não grava cliente como B (WITH CHECK)

Tenant = org_id (a firma contábil). Pulado sem DATABASE_URL (Postgres real).

Nota: clientes.org_id é FK → orgs, então as orgs são criadas no setup. E o
INSERT é flushado logo após cada set_config (o SET LOCAL vale por transação;
adiar até o commit faria o WITH CHECK usar a org errada).
"""
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.db.models import Base, Cliente, DocumentoFiscal, Org

_RAW = os.environ.get("DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not _RAW, reason="RLS exige DATABASE_URL (Postgres real)")

ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"
_APP_PW = "rls_poc_app_pw"
_SQL = Path(__file__).resolve().parent.parent / "db" / "rls" / "org_isolation.sql"


def _url(driver: str, user: str | None = None, pw: str | None = None) -> str:
    p = urlsplit(_RAW.replace("postgresql+asyncpg://", "postgresql://", 1))
    host = p.hostname or "localhost"
    port = f":{p.port}" if p.port else ""
    u = user or p.username or "postgres"
    w = pw if pw is not None else (p.password or "")
    return urlunsplit((driver, f"{u}:{w}@{host}{port}", p.path or "/postgres", "", ""))


@pytest_asyncio.fixture
async def app_maker():
    import asyncpg

    # Schema real via SQLAlchemy (owner); RLS via asyncpg (aceita DO blocks / multi-stmt).
    owner = create_async_engine(_url("postgresql+asyncpg"))
    async with owner.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    conn = await asyncpg.connect(_url("postgresql"))
    try:
        await conn.execute(_SQL.read_text(encoding="utf-8"))
        await conn.execute(f"ALTER ROLE app_orgconc PASSWORD '{_APP_PW}'")
        await conn.execute("TRUNCATE public.clientes CASCADE")
    finally:
        await conn.close()

    # Orgs precisam existir (FK clientes.org_id → orgs). Criadas como owner (orgs
    # não tem RLS); idempotente entre testes.
    async with async_sessionmaker(owner, expire_on_commit=False)() as s, s.begin():
        for oid, nome in ((ORG_A, "Org A"), (ORG_B, "Org B")):
            if await s.get(Org, uuid.UUID(oid)) is None:
                s.add(Org(id=uuid.UUID(oid), nome=nome))
    await owner.dispose()

    # Sessões como app_orgconc (NOBYPASSRLS → a RLS se aplica de verdade).
    engine = create_async_engine(_url("postgresql+asyncpg", "app_orgconc", _APP_PW))
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _criar_cliente(s, org_id: str, nome: str) -> None:
    await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": org_id})
    s.add(Cliente(org_id=uuid.UUID(org_id), nome=nome))
    await s.flush()  # INSERT agora, com o set_config corrente (não no commit)


@pytest.mark.asyncio
async def test_org_nao_le_cliente_de_outro(app_maker):
    """Org A cria cliente; org B não o enxerga."""
    async with app_maker() as s, s.begin():
        await _criar_cliente(s, ORG_A, "Cliente Alfa")
        await _criar_cliente(s, ORG_B, "Cliente Beta")
    async with app_maker() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": ORG_A})
        nomes = (await s.execute(text("SELECT nome FROM public.clientes"))).scalars().all()
    assert "Cliente Alfa" in nomes
    assert "Cliente Beta" not in nomes, "VAZAMENTO entre orgs na tabela clientes"


@pytest.mark.asyncio
async def test_sem_org_zero_clientes(app_maker):
    """Falha FECHADA: sem app.org_id setado, clientes não retorna nada."""
    async with app_maker() as s, s.begin():
        await _criar_cliente(s, ORG_A, "Existe")
    async with app_maker() as s, s.begin():
        rows = (await s.execute(text("SELECT 1 FROM public.clientes"))).all()
    assert rows == [], "FALHA ABERTA: sem tenant a query devolveu clientes"


@pytest.mark.asyncio
async def test_with_check_bloqueia_cliente_cruzado(app_maker):
    """Org A não consegue gravar cliente marcado como B (WITH CHECK)."""
    with pytest.raises(Exception):
        async with app_maker() as s, s.begin():
            await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": ORG_A})
            s.add(Cliente(org_id=uuid.UUID(ORG_B), nome="Intruso"))
            await s.flush()  # dispara o INSERT → WITH CHECK barra a org cruzada


@pytest.mark.asyncio
async def test_org_nao_le_documento_fiscal_de_outro(app_maker):
    """Tabela fiscal (org_id na migration 020): org A não vê doc fiscal de B."""
    async with app_maker() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": ORG_A})
        cli = Cliente(org_id=uuid.UUID(ORG_A), nome="Cliente Doc A")
        s.add(cli)
        await s.flush()
        s.add(DocumentoFiscal(
            org_id=uuid.UUID(ORG_A), cliente_id=cli.id,
            tipo="NF-e", modelo="55", chave="A" * 44, valor_total=100,
        ))
        await s.flush()
    # Org B não enxerga o documento de A.
    async with app_maker() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": ORG_B})
        n_b = (await s.execute(text("SELECT count(*) FROM public.documento_fiscal"))).scalar_one()
    assert n_b == 0, "VAZAMENTO entre orgs na tabela documento_fiscal"
    # Org A enxerga o seu.
    async with app_maker() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": ORG_A})
        n_a = (await s.execute(text("SELECT count(*) FROM public.documento_fiscal"))).scalar_one()
    assert n_a == 1
