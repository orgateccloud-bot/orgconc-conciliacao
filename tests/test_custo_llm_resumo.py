"""Testes unitarios para api/db/metrics.custo_llm_resumo — previsao de gastos.

Usa uma AsyncSession falsa (sem banco) para isolar a aritmetica de burn rate e
projecao. 'Hoje' e congelado via monkeypatch para tornar as projecoes
deterministicas.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.db import metrics as crud_metrics


def _mock_db_rows(rows: list) -> MagicMock:
    """AsyncSession mockado cujo .execute(...).all() retorna `rows`."""
    db = MagicMock()
    result_mock = MagicMock()
    result_mock.all = MagicMock(return_value=rows)
    db.execute = AsyncMock(return_value=result_mock)
    return db


def _row(d: date, custo: str, chamadas: int) -> SimpleNamespace:
    return SimpleNamespace(dia=d, custo_usd=Decimal(custo), chamadas=chamadas)


@pytest.fixture
def hoje(monkeypatch) -> date:
    """Congela 'hoje' em 2026-05-29 (UTC). Maio tem 31 dias → 2 dias restantes."""
    fixo = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(crud_metrics, "_now_utc", lambda: fixo)
    return fixo.date()


@pytest.mark.asyncio
async def test_resumo_vazio_zera_tudo(hoje):
    r = await crud_metrics.custo_llm_resumo(_mock_db_rows([]), periodo_dias=30)
    assert r["total_periodo_usd"] == 0.0
    assert r["total_chamadas"] == 0
    assert r["custo_hoje_usd"] == 0.0
    assert r["burn_rate_diario_usd"] == 0.0
    assert r["projecao_30d_usd"] == 0.0
    assert r["mes_corrente"]["projecao_fim_mes_usd"] == 0.0
    assert r["serie_diaria"] == []


@pytest.mark.asyncio
async def test_burn_rate_media_7_dias(hoje):
    # 7 dias seguidos com 7.0 USD/dia → media diaria = 7.0; projecao 30d = 210
    rows = [_row(hoje - timedelta(days=i), "7.0", 2) for i in range(7)]
    r = await crud_metrics.custo_llm_resumo(_mock_db_rows(rows), periodo_dias=30)
    assert r["burn_rate_diario_usd"] == pytest.approx(7.0)
    assert r["projecao_30d_usd"] == pytest.approx(210.0)
    assert r["total_chamadas"] == 14


@pytest.mark.asyncio
async def test_burn_rate_inclui_dias_zerados(hoje):
    # So 1 dia (hoje) com 7.0 USD na janela de 7 → media = 7/7 = 1.0 (dias vazios contam 0)
    r = await crud_metrics.custo_llm_resumo(_mock_db_rows([_row(hoje, "7.0", 1)]), periodo_dias=30)
    assert r["burn_rate_diario_usd"] == pytest.approx(1.0)
    assert r["custo_hoje_usd"] == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_projecao_fim_mes(hoje):
    # Hoje (29/mai) com 10 USD; maio = 31 dias → 2 dias restantes; burn = 10/7
    r = await crud_metrics.custo_llm_resumo(_mock_db_rows([_row(hoje, "10.0", 1)]), periodo_dias=30)
    mc = r["mes_corrente"]
    assert mc["dias_no_mes"] == 31
    assert mc["dias_restantes"] == 2
    assert mc["custo_ate_agora_usd"] == pytest.approx(10.0)
    burn = round(10.0 / 7, 4)
    assert r["burn_rate_diario_usd"] == pytest.approx(burn)
    assert mc["projecao_fim_mes_usd"] == pytest.approx(round(10.0 + burn * 2, 4))


@pytest.mark.asyncio
async def test_serie_limitada_ao_periodo_de_exibicao(hoje):
    # periodo_dias=3 → serie so mostra hoje, ontem e anteontem, mas o custo do mes
    # (calculado fora da janela de exibicao) ainda soma um lancamento mais antigo.
    # Rows em ordem crescente de dia — espelha o ORDER BY dia da query real.
    rows = [
        _row(hoje - timedelta(days=10), "100.0", 1),  # fora da exibicao, dentro do mes
        _row(hoje - timedelta(days=2), "3.0", 1),
        _row(hoje - timedelta(days=1), "2.0", 1),
        _row(hoje, "1.0", 1),
    ]
    r = await crud_metrics.custo_llm_resumo(_mock_db_rows(rows), periodo_dias=3)
    # Serie de exibicao: apenas os 3 dias recentes
    assert [d["data"] for d in r["serie_diaria"]] == [
        (hoje - timedelta(days=2)).isoformat(),
        (hoje - timedelta(days=1)).isoformat(),
        hoje.isoformat(),
    ]
    assert r["total_periodo_usd"] == pytest.approx(6.0)  # 1+2+3, exclui o de 10 dias atras
    # Mas o gasto do mes inclui o lancamento antigo (mesmo mes de maio)
    assert r["mes_corrente"]["custo_ate_agora_usd"] == pytest.approx(106.0)
