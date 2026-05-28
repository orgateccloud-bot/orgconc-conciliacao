"""Testes para api/matchers/guia.py e api/matchers/contrato.py — estágios 4 e 5.

Usa mocks de AsyncSession para evitar dependência de banco real.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.db.models import Contrato, GuiaTributo
from api.matchers.cascata import Resultado, Transacao
from api.matchers.contrato import resolver as resolver_contrato
from api.matchers.guia import resolver as resolver_guia


CLIENTE_ID = uuid.uuid4()


def _mock_db_returning(linhas: list):
    """Cria um AsyncSession mockado que retorna `linhas` no .execute().scalars().all()."""
    db = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=linhas)
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=scalars_mock)
    db.execute = AsyncMock(return_value=result_mock)
    return db


def _resultado_guia(valor: float, tipo: str = "DARF") -> Resultado:
    t = Transacao(
        data="2026-05-10", tipo="DEBIT", valor=-abs(valor),
        fitid=f"X{int(valor)}", memo=f"{tipo} PAGAMENTO", nome=f"{tipo} PARCELAMENTO",
    )
    return Resultado(t, estagio=4, metodo="match_guia_tributo", chave=tipo)


def _resultado_contrato(valor: float, memo: str = "DEB.CONV.SEGUROS") -> Resultado:
    t = Transacao(
        data="2026-05-10", tipo="DEBIT", valor=-abs(valor),
        fitid=f"C{int(valor)}", memo=memo, nome="Seguro mensal",
    )
    return Resultado(t, estagio=5, metodo="match_contrato")


# ────────────────────────────────────────────────────────────────────────
# Guia tributária
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_guia_resolvida_match_unico():
    g = GuiaTributo(
        id=uuid.uuid4(), cliente_id=CLIENTE_ID, tipo="DARF",
        valor=Decimal("1234.56"), competencia="2026-04",
        conta_contabil="2.1.3.01.001", ativo=True,
    )
    db = _mock_db_returning([g])
    res = [_resultado_guia(1234.56, "DARF")]
    saida = await resolver_guia(res, db, CLIENTE_ID)
    assert len(saida) == 1
    assert saida[0].status == "RESOLVIDO"
    assert saida[0].tipo == "DARF"
    assert saida[0].conta_contabil == "2.1.3.01.001"


@pytest.mark.asyncio
async def test_guia_nao_encontrada():
    db = _mock_db_returning([])
    res = [_resultado_guia(999.99, "DAS")]
    saida = await resolver_guia(res, db, CLIENTE_ID)
    assert len(saida) == 1
    assert saida[0].status == "GUIA_NAO_ENCONTRADA"
    assert "999.99" in saida[0].flag


@pytest.mark.asyncio
async def test_guia_ambigua_sem_desempate():
    """2 guias no mesmo valor, ambas DAS — não dá para desempatar."""
    g1 = GuiaTributo(id=uuid.uuid4(), cliente_id=CLIENTE_ID, tipo="DAS",
                     valor=Decimal("500.00"), ativo=True)
    g2 = GuiaTributo(id=uuid.uuid4(), cliente_id=CLIENTE_ID, tipo="DAS",
                     valor=Decimal("500.00"), ativo=True)
    db = _mock_db_returning([g1, g2])
    res = [_resultado_guia(500.00, "DAS")]
    saida = await resolver_guia(res, db, CLIENTE_ID)
    assert saida[0].status == "GUIA_AMBIGUA"


@pytest.mark.asyncio
async def test_guia_desempate_por_tipo():
    """2 guias no mesmo valor mas tipos diferentes; cascata extraiu DARF → escolhe DARF."""
    g_darf = GuiaTributo(id=uuid.uuid4(), cliente_id=CLIENTE_ID, tipo="DARF",
                         valor=Decimal("100.00"), competencia="2026-04", ativo=True)
    g_das = GuiaTributo(id=uuid.uuid4(), cliente_id=CLIENTE_ID, tipo="DAS",
                        valor=Decimal("100.00"), ativo=True)
    db = _mock_db_returning([g_darf, g_das])
    res = [_resultado_guia(100.00, "DARF")]
    saida = await resolver_guia(res, db, CLIENTE_ID)
    assert saida[0].status == "RESOLVIDO"
    assert saida[0].tipo == "DARF"
    assert saida[0].competencia == "2026-04"


@pytest.mark.asyncio
async def test_guia_filtra_so_estagio_4():
    """resolver_guia ignora resultados de outros métodos."""
    t = Transacao(data="2026-05-10", tipo="DEBIT", valor=-100, fitid="x", memo="", nome="")
    r_outro = Resultado(t, estagio=2, metodo="match_nfe", chave="999")
    db = _mock_db_returning([])
    saida = await resolver_guia([r_outro], db, CLIENTE_ID)
    assert saida == []
    db.execute.assert_not_called()


# ────────────────────────────────────────────────────────────────────────
# Contrato recorrente
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contrato_resolvido_match_unico():
    c = Contrato(
        id=uuid.uuid4(), cliente_id=CLIENTE_ID, descricao="Seguro frota",
        valor=Decimal("780.00"), periodicidade="mensal",
        conta_contabil="3.1.2.04.005", ativo=True,
    )
    db = _mock_db_returning([c])
    res = [_resultado_contrato(780.00)]
    saida = await resolver_contrato(res, db, CLIENTE_ID)
    assert len(saida) == 1
    assert saida[0].status == "RESOLVIDO"
    assert saida[0].descricao == "Seguro frota"


@pytest.mark.asyncio
async def test_contrato_nao_encontrado():
    db = _mock_db_returning([])
    res = [_resultado_contrato(9999.99)]
    saida = await resolver_contrato(res, db, CLIENTE_ID)
    assert saida[0].status == "CONTRATO_NAO_ENCONTRADO"


@pytest.mark.asyncio
async def test_contrato_desempate_por_padrao_memo():
    """2 contratos mesmo valor; padrão 'SEGURO' está no memo → escolhe seguro."""
    c_aluguel = Contrato(
        id=uuid.uuid4(), cliente_id=CLIENTE_ID, descricao="Aluguel",
        valor=Decimal("780.00"), padrao_memo="ALUGUEL", ativo=True,
    )
    c_seguro = Contrato(
        id=uuid.uuid4(), cliente_id=CLIENTE_ID, descricao="Seguro frota",
        valor=Decimal("780.00"), padrao_memo="SEGURO", ativo=True,
    )
    db = _mock_db_returning([c_aluguel, c_seguro])
    res = [_resultado_contrato(780.00, memo="DEB.CONV.SEGUROS")]
    saida = await resolver_contrato(res, db, CLIENTE_ID)
    assert saida[0].status == "RESOLVIDO"
    assert saida[0].descricao == "Seguro frota"


@pytest.mark.asyncio
async def test_contrato_ambiguo_sem_padrao():
    """2 contratos mesmo valor, nenhum padrão_memo casa → ambíguo."""
    c1 = Contrato(id=uuid.uuid4(), cliente_id=CLIENTE_ID, descricao="A",
                  valor=Decimal("100.00"), padrao_memo="XXX", ativo=True)
    c2 = Contrato(id=uuid.uuid4(), cliente_id=CLIENTE_ID, descricao="B",
                  valor=Decimal("100.00"), padrao_memo="YYY", ativo=True)
    db = _mock_db_returning([c1, c2])
    res = [_resultado_contrato(100.00, memo="DEB GENERICO")]
    saida = await resolver_contrato(res, db, CLIENTE_ID)
    assert saida[0].status == "CONTRATO_AMBIGUO"


@pytest.mark.asyncio
async def test_contrato_filtra_so_estagio_5():
    """resolver_contrato ignora resultados de outros métodos."""
    t = Transacao(data="2026-05-10", tipo="DEBIT", valor=-100, fitid="x", memo="", nome="")
    r_outro = Resultado(t, estagio=3, metodo="tarifa_bancaria")
    db = _mock_db_returning([])
    saida = await resolver_contrato([r_outro], db, CLIENTE_ID)
    assert saida == []
    db.execute.assert_not_called()
