"""Testes para api/matchers/contrapartes.py — consulta por alias (estágio 6).

Cobre:
- _normaliza_alias (limpeza de prefixos do memo bancário)
- _escapa_like (escape de curingas %/_ e \\) — W4 #28
- consultar_por_alias:
    - alias curto → None sem ir ao banco
    - 1 candidato → CadastroContraparte; 0 ou >1 → None
    - escape de curingas no padrão ILIKE (não casa indevidamente)
    - filtro de tenant por org_id (explícito e via contexto RLS) — W4 #15

Usa mocks de AsyncSession (não depende de banco real).
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.db.models import Cliente
from api.matchers.contrapartes import (
    CadastroContraparte,
    _escapa_like,
    _normaliza_alias,
    consultar_por_alias,
)


CLIENTE_ID = uuid.uuid4()


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _mock_db(candidatos: list[Cliente]):
    """AsyncSession mockado: .execute().scalars().all() devolve `candidatos`."""
    db = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=candidatos)
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=scalars_mock)
    db.execute = AsyncMock(return_value=result_mock)
    return db


def _cliente(nome: str, org_id: uuid.UUID | None = None) -> Cliente:
    return Cliente(id=uuid.uuid4(), nome=nome, cnpj=None, ativo=True, org_id=org_id)


def _filtra_org_na_where(db) -> bool:
    """True se a cláusula WHERE da última query restringe por clientes.org_id."""
    stmt = db.execute.await_args.args[0]
    where_sql = str(stmt.whereclause.compile(compile_kwargs={"literal_binds": False}))
    return "clientes.org_id" in where_sql


def _params_da_consulta(db) -> dict:
    """Parâmetros vinculados da última query (inclui o padrão do ILIKE)."""
    stmt = db.execute.await_args.args[0]
    return stmt.compile().params


# ────────────────────────────────────────────────────────────────────────
# _normaliza_alias
# ────────────────────────────────────────────────────────────────────────


def test_normaliza_alias_vazio():
    assert _normaliza_alias("") == ""
    assert _normaliza_alias(None) == ""  # type: ignore[arg-type]


def test_normaliza_alias_remove_prefixo_fav():
    assert _normaliza_alias("FAV.: FULANO DE TAL") == "FULANO DE TAL"
    assert _normaliza_alias("FAVORECIDO: BELTRANO") == "BELTRANO"


def test_normaliza_alias_sem_prefixo_inalterado():
    assert _normaliza_alias("ACME COMERCIO LTDA") == "ACME COMERCIO LTDA"


# ────────────────────────────────────────────────────────────────────────
# _escapa_like — W4 #28
# ────────────────────────────────────────────────────────────────────────


def test_escapa_like_porcento():
    assert _escapa_like("EMPRESA 100%") == "EMPRESA 100\\%"


def test_escapa_like_underscore():
    assert _escapa_like("FULANO_DE_TAL") == "FULANO\\_DE\\_TAL"


def test_escapa_like_backslash_primeiro():
    # A barra invertida é escapada antes dos curingas (não duplica os escapes).
    assert _escapa_like("A\\B_C%") == "A\\\\B\\_C\\%"


def test_escapa_like_sem_curingas_inalterado():
    assert _escapa_like("ACME LTDA") == "ACME LTDA"


# ────────────────────────────────────────────────────────────────────────
# consultar_por_alias — ramos básicos
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consultar_alias_curto_retorna_none():
    """Alias com < 4 chars após normalização → None, sem ir ao banco."""
    db = _mock_db([])
    out = await consultar_por_alias(db, CLIENTE_ID, "ABC")
    assert out is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_consultar_alias_um_candidato():
    cli = _cliente("ACME COMERCIO LTDA")
    db = _mock_db([cli])
    out = await consultar_por_alias(db, CLIENTE_ID, "ACME COMERCIO")
    assert isinstance(out, CadastroContraparte)
    assert out.nome_real == "ACME COMERCIO LTDA"
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_consultar_alias_zero_candidatos():
    db = _mock_db([])
    out = await consultar_por_alias(db, CLIENTE_ID, "INEXISTENTE")
    assert out is None


@pytest.mark.asyncio
async def test_consultar_alias_ambiguo_retorna_none():
    """Mais de 1 candidato → ambíguo → None (não chuta)."""
    db = _mock_db([_cliente("ACME UM"), _cliente("ACME DOIS")])
    out = await consultar_por_alias(db, CLIENTE_ID, "ACME")
    assert out is None


# ────────────────────────────────────────────────────────────────────────
# consultar_por_alias — escape de curingas — W4 #28
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consultar_alias_escapa_underscore_no_padrao():
    """Alias com '_' vira padrão com curinga escapado (\\_), não '_' literal LIKE."""
    db = _mock_db([])
    await consultar_por_alias(db, CLIENTE_ID, "FULANO_DE_TAL")
    params = _params_da_consulta(db)
    padroes = [v for v in params.values() if isinstance(v, str) and "FULANO" in v]
    assert padroes, "padrão do ILIKE não encontrado nos parâmetros"
    assert "\\_" in padroes[0]
    assert "FULANO_DE" not in padroes[0]  # o '_' cru não escapa para o padrão


@pytest.mark.asyncio
async def test_consultar_alias_escapa_porcento_no_padrao():
    db = _mock_db([])
    await consultar_por_alias(db, CLIENTE_ID, "EMPRESA 100%")
    params = _params_da_consulta(db)
    padroes = [v for v in params.values() if isinstance(v, str) and "EMPRESA" in v]
    assert padroes
    assert "\\%" in padroes[0]


# ────────────────────────────────────────────────────────────────────────
# consultar_por_alias — filtro de tenant (org_id) — W4 #15
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consultar_alias_filtra_por_org_explicito():
    org = uuid.uuid4()
    cli = _cliente("ACME DO TENANT", org_id=org)
    db = _mock_db([cli])
    out = await consultar_por_alias(db, CLIENTE_ID, "ACME DO TENANT", org_id=org)
    assert out is not None
    assert _filtra_org_na_where(db)


@pytest.mark.asyncio
async def test_consultar_alias_sem_org_consulta_global():
    cli = _cliente("ACME GLOBAL")
    db = _mock_db([cli])
    out = await consultar_por_alias(db, CLIENTE_ID, "ACME GLOBAL")
    assert out is not None
    assert not _filtra_org_na_where(db)


@pytest.mark.asyncio
async def test_consultar_alias_usa_org_do_contexto_rls():
    from api.db.rls_context import reset_org_context, set_org_context

    org = uuid.uuid4()
    token = set_org_context(str(org))
    try:
        cli = _cliente("ACME CONTEXTO", org_id=org)
        db = _mock_db([cli])
        out = await consultar_por_alias(db, CLIENTE_ID, "ACME CONTEXTO")
        assert out is not None
        assert _filtra_org_na_where(db)
    finally:
        reset_org_context(token)
