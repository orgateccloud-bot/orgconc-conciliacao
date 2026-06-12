"""Testes do UPSERT idempotente de salvar_apuracao (IC-02 §3.2, migration 022).

Sem DB real: mocka a AsyncSession e inspeciona o statement gerado — prova que é
um INSERT ... ON CONFLICT (documento_id, versao_base) DO UPDATE e que as chaves
de identidade (documento_id/versao_base/id/org_id) ficam FORA do SET.
"""
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from api.schemas_cbs_ibs import ItemOperacao, OperacaoFiscalInput
from api.services.calculadora_cbs_ibs import _apurar_stub
from api.services.fiscal_persistence import salvar_apuracao

DOC_ID = "7e3f1a2b-9c4d-4e5f-8a6b-1c2d3e4f5a6b"


def _apuracao():
    inp = OperacaoFiscalInput(
        documento_id=DOC_ID,
        uf="GO",
        municipio_ibge="5208707",
        data_fato_gerador=date(2026, 2, 1),
        itens=[ItemOperacao(numero=1, ncm="22021000", cst="000",
                            cClassTrib="000001", base_calculo=1000.0)],
    )
    return _apurar_stub(inp)


def _db_devolvendo(row_id: uuid.UUID) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = row_id
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_salvar_apuracao_retorna_id_do_banco():
    esperado = uuid.uuid4()
    db = _db_devolvendo(esperado)
    out = await salvar_apuracao(db, _apuracao(), org_id=uuid.uuid4())
    assert out == esperado
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_salvar_apuracao_gera_upsert_on_conflict():
    db = _db_devolvendo(uuid.uuid4())
    await salvar_apuracao(db, _apuracao())
    stmt = db.execute.await_args.args[0]
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "INSERT INTO apuracao_cbs_ibs" in sql
    assert "ON CONFLICT (documento_id, versao_base) DO UPDATE" in sql
    assert "RETURNING apuracao_cbs_ibs.id" in sql


@pytest.mark.asyncio
async def test_upsert_nao_sobrescreve_chaves_de_identidade():
    # No DO UPDATE SET não podem aparecer documento_id/versao_base/id/org_id —
    # a linha existente mantém identidade e tenant; só os valores são atualizados.
    db = _db_devolvendo(uuid.uuid4())
    await salvar_apuracao(db, _apuracao(), org_id=uuid.uuid4())
    stmt = db.execute.await_args.args[0]
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    set_clause = sql.split("DO UPDATE SET", 1)[1].split("RETURNING", 1)[0]
    for chave in ("documento_id", "versao_base", " id ", "org_id"):
        assert chave not in set_clause, f"{chave!r} não pode estar no SET"
    # E os valores apuráveis SÃO atualizados.
    assert "v_tot_trib" in set_clause
    assert "payload_hash" in set_clause


@pytest.mark.asyncio
async def test_valores_persistidos_espelham_a_apuracao():
    db = _db_devolvendo(uuid.uuid4())
    ap = _apuracao()
    await salvar_apuracao(db, ap)
    stmt = db.execute.await_args.args[0]
    params = stmt.compile(dialect=postgresql.dialect()).params
    assert params["documento_id"] == uuid.UUID(DOC_ID)
    assert params["versao_base"] == ap.versao_base
    assert params["v_tot_trib"] == ap.vTotTrib
    assert params["payload_hash"] == ap.payload_hash
    assert params["memoria_calculo"]["cbs"] == ap.gCBS.memoriaCalculo
