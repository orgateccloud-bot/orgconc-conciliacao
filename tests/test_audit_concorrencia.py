"""test_audit_concorrencia.py — PROVA que a cadeia de hash sobrevive a writes
concorrentes (achados #1, #4).

Antes do fix, `_buscar_ultimo_hash` lia o último hash SEM lock e SEM filtro de
org: dois writers concorrentes liam o MESMO prev_hash e gravavam dois eventos
forkando a cadeia (dois eventos com o mesmo prev). Agora o SELECT usa
`with_for_update()` filtrado por org, na MESMA transação do INSERT — os writers
da mesma org serializam e a cadeia fica linear.

Este teste precisa de Postgres REAL (o lock de linha não existe em SQLite/mock):
é PULADO sem DATABASE_URL, no mesmo molde de test_rls_real_tables.py. Cada task
concorrente usa a SUA própria sessão/transação (conexões distintas) — é o que
expõe a corrida; reusar uma sessão serializaria por construção.

Conecta como OWNER (postgres) de propósito: o foco é o lock da cadeia, não a
RLS. audit_events não tem cliente_id/FK obrigatória além de org_id → orgs, então
basta criar as orgs no setup.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.db.models import AuditEvent, Base, Org
from api.services.audit import registrar_audit, verificar_cadeia, GENESIS_HASH
from api.services.auth import TokenPayload

_RAW = os.environ.get("DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not _RAW, reason="concorrência da cadeia exige DATABASE_URL (Postgres real)"
)

ORG_A = "33333333-3333-3333-3333-333333333333"
ORG_B = "44444444-4444-4444-4444-444444444444"


def _url(driver: str) -> str:
    p = urlsplit(_RAW.replace("postgresql+asyncpg://", "postgresql://", 1))
    host = p.hostname or "localhost"
    port = f":{p.port}" if p.port else ""
    u = p.username or "postgres"
    w = p.password or ""
    return urlunsplit((driver, f"{u}:{w}@{host}{port}", p.path or "/postgres", "", ""))


@pytest_asyncio.fixture
async def maker():
    engine = create_async_engine(_url("postgresql+asyncpg"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    # Orgs (FK audit_events.org_id → orgs) + limpeza da trilha.
    async with sm() as s, s.begin():
        for oid, nome in ((ORG_A, "Org Conc A"), (ORG_B, "Org Conc B")):
            if await s.get(Org, uuid.UUID(oid)) is None:
                s.add(Org(id=uuid.UUID(oid), nome=nome))
        await s.execute(text(
            "DELETE FROM public.audit_events WHERE org_id IN (:a, :b)"
        ), {"a": ORG_A, "b": ORG_B})
    try:
        yield sm
    finally:
        # Limpa o que o teste gravou (não derruba o schema compartilhado).
        async with sm() as s, s.begin():
            await s.execute(text(
                "DELETE FROM public.audit_events WHERE org_id IN (:a, :b)"
            ), {"a": ORG_A, "b": ORG_B})
        await engine.dispose()


async def _gravar_um(sm, *, org_id: str, i: int) -> None:
    """1 evento numa transação própria (sessão dedicada → corrida real)."""
    actor = TokenPayload(sub=f"u{i}", email=f"u{i}@x.com", role="user", org_id=org_id)
    async with sm() as s, s.begin():
        await registrar_audit(s, action="conc.write", payload={"i": i}, actor=actor)


async def _eventos_da_org(sm, org_id: str) -> list[AuditEvent]:
    async with sm() as s:
        q = (
            select(AuditEvent)
            .where(AuditEvent.org_id == uuid.UUID(org_id))
            .order_by(AuditEvent.ts.asc(), AuditEvent.payload_hash.asc())
        )
        return list((await s.execute(q)).scalars().all())


@pytest.mark.asyncio
async def test_writes_concorrentes_mantem_cadeia_integra(maker):
    """N writes concorrentes na MESMA org → cadeia linear, sem fork."""
    N = 25
    await asyncio.gather(*[_gravar_um(maker, org_id=ORG_A, i=i) for i in range(N)])

    eventos = await _eventos_da_org(maker, ORG_A)
    assert len(eventos) == N, f"esperava {N} eventos, gravou {len(eventos)}"

    # Nenhum prev_hash repetido (fork = dois eventos apontando para o mesmo pai).
    prevs = [e.prev_hash for e in eventos]
    assert len(set(prevs)) == len(prevs), "FORK: prev_hash repetido entre writers concorrentes"

    # Exatamente um genesis e cadeia verificável.
    assert prevs.count(GENESIS_HASH) == 1, "deveria haver exatamente um evento genesis"
    ok, motivo = verificar_cadeia(eventos)
    assert ok, f"cadeia quebrada após writes concorrentes: {motivo}"


@pytest.mark.asyncio
async def test_writes_concorrentes_duas_orgs_cadeias_independentes(maker):
    """Writes intercalados de duas orgs → cada org tem sua cadeia íntegra (#4)."""
    N = 12
    tarefas = []
    for i in range(N):
        tarefas.append(_gravar_um(maker, org_id=ORG_A, i=i))
        tarefas.append(_gravar_um(maker, org_id=ORG_B, i=i))
    await asyncio.gather(*tarefas)

    for org in (ORG_A, ORG_B):
        eventos = await _eventos_da_org(maker, org)
        assert len(eventos) == N
        ok, motivo = verificar_cadeia(eventos)
        assert ok, f"cadeia da org {org} quebrada: {motivo}"
        assert [e.prev_hash for e in eventos].count(GENESIS_HASH) == 1
