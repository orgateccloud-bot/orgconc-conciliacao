"""Testes para api/core/llm_metrics.py — calculo de custo e acumulador diario."""
from __future__ import annotations

import logging
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.core import llm_metrics


@pytest.fixture(autouse=True)
def _limpar_estado():
    llm_metrics.resetar_acumulador_para_testes()
    for var in [
        "ORGCONC_LLM_COST_ALERT_USD",
        "ORGCONC_LLM_PRICE_FABLE_IN", "ORGCONC_LLM_PRICE_FABLE_OUT",
        "ORGCONC_LLM_PRICE_SONNET_IN", "ORGCONC_LLM_PRICE_SONNET_OUT",
        "ORGCONC_LLM_PRICE_HAIKU_IN", "ORGCONC_LLM_PRICE_HAIKU_OUT",
    ]:
        os.environ.pop(var, None)
    yield
    llm_metrics.resetar_acumulador_para_testes()


def test_calcular_custo_fable_usa_default():
    m = llm_metrics.calcular_custo("claude-fable-5", 1_000_000, 1_000_000)
    # Fable 5 = $10/$50 (tabela oficial 2026)
    assert m["cost_input_usd"] == 10.0
    assert m["cost_output_usd"] == 50.0
    assert m["cost_total_usd"] == 60.0
    assert m["model_id"] == "claude-fable-5"


def test_calcular_custo_sonnet_pequeno():
    m = llm_metrics.calcular_custo("claude-sonnet-4-6", 10_000, 5_000)
    # 10k input * 3/1M = 0.03; 5k output * 15/1M = 0.075; total 0.105
    assert m["cost_total_usd"] == pytest.approx(0.105, rel=1e-3)


def test_calcular_custo_haiku_zero_tokens():
    m = llm_metrics.calcular_custo("claude-haiku-4-5-20251001", 0, 0)
    assert m["cost_total_usd"] == 0.0


def test_calcular_custo_modelo_desconhecido_cai_em_haiku():
    # Fallback: modelo nao reconhecido vira haiku (mais barato → mais seguro)
    m = llm_metrics.calcular_custo("modelo-novo-2099", 1_000_000, 1_000_000)
    assert m["cost_input_usd"] == 1.0
    assert m["cost_output_usd"] == 5.0


def test_override_preco_via_env():
    os.environ["ORGCONC_LLM_PRICE_FABLE_IN"] = "20.0"
    os.environ["ORGCONC_LLM_PRICE_FABLE_OUT"] = "100.0"
    m = llm_metrics.calcular_custo("claude-fable-5", 1_000_000, 1_000_000)
    assert m["cost_input_usd"] == 20.0
    assert m["cost_output_usd"] == 100.0


def test_override_preco_invalido_cai_em_default(caplog):
    os.environ["ORGCONC_LLM_PRICE_FABLE_IN"] = "nao-eh-numero"
    with caplog.at_level(logging.WARNING):
        m = llm_metrics.calcular_custo("claude-fable-5", 1_000_000, 0)
    assert m["cost_input_usd"] == 10.0


def test_registrar_uso_loga_estruturado(caplog):
    with caplog.at_level(logging.INFO, logger="orgconc.llm.metrics"):
        metrics = llm_metrics.registrar_uso(
            "claude-sonnet-4-6", "Sonnet 4.6", 10_000, 5_000, duracao_ms=120.5
        )
    assert metrics["cost_total_usd"] == pytest.approx(0.105, rel=1e-3)
    assert metrics["cost_dia_usd"] == pytest.approx(0.105, rel=1e-3)
    rec = next(r for r in caplog.records if r.message == "llm_uso")
    assert rec.llm_model == "claude-sonnet-4-6"
    assert rec.llm_input_tokens == 10_000
    assert rec.llm_duracao_ms == 120.5


def test_acumulador_soma_no_mesmo_dia():
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)
    metrics2 = llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)
    # 100k * (1+5)/1M = 0.6 por chamada → 1.2 acumulado
    assert metrics2["cost_dia_usd"] == pytest.approx(1.2, rel=1e-3)


def test_threshold_dispara_warning_uma_vez(caplog):
    os.environ["ORGCONC_LLM_COST_ALERT_USD"] = "0.5"
    with caplog.at_level(logging.WARNING, logger="orgconc.llm.metrics"):
        llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)  # 0.6 USD
        llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)  # 1.2 USD
    avisos = [r for r in caplog.records if r.message == "llm_custo_threshold_atingido"]
    assert len(avisos) == 1  # so dispara 1x por dia


def test_threshold_zero_nao_dispara(caplog):
    os.environ["ORGCONC_LLM_COST_ALERT_USD"] = "0"
    with caplog.at_level(logging.WARNING, logger="orgconc.llm.metrics"):
        llm_metrics.registrar_uso("claude-fable-5", "F", 1_000_000, 1_000_000)
    assert not any(r.message == "llm_custo_threshold_atingido" for r in caplog.records)


# --- Acumulador: persistencia incremental por delta (suporte a workers > 1) ---


def test_delta_reflete_total_nao_persistido():
    # Duas chamadas haiku de 0.6 USD cada → total 1.2, 2 chamadas, nada persistido
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)
    dia, delta_usd, delta_chamadas = llm_metrics._ACUMULADOR.delta_para_persistir()
    assert dia  # dia ISO nao vazio
    assert delta_usd == pytest.approx(1.2, rel=1e-3)
    assert delta_chamadas == 2


def test_confirmar_persistido_zera_delta():
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)
    acc = llm_metrics._ACUMULADOR
    dia, delta_usd, delta_chamadas = acc.delta_para_persistir()
    acc.confirmar_persistido(dia, delta_usd, delta_chamadas)
    # Sem novas chamadas apos confirmar → nada a persistir
    _, d2_usd, d2_chamadas = acc.delta_para_persistir()
    assert d2_chamadas == 0
    assert d2_usd == pytest.approx(0.0, abs=1e-9)


def test_delta_incremental_apos_confirmar():
    acc = llm_metrics._ACUMULADOR
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)  # 0.6
    dia, d_usd, d_ch = acc.delta_para_persistir()
    acc.confirmar_persistido(dia, d_usd, d_ch)
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)  # +0.6
    _, d2_usd, d2_ch = acc.delta_para_persistir()
    assert d2_ch == 1  # so o incremento novo
    assert d2_usd == pytest.approx(0.6, rel=1e-3)


def test_confirmar_persistido_dia_diferente_eh_noop():
    # Se o dia virou entre o peek e o confirm, o delta antigo nao e remarcado.
    acc = llm_metrics._ACUMULADOR
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)
    dia, d_usd, d_ch = acc.delta_para_persistir()
    acc.confirmar_persistido("1999-01-01", d_usd, d_ch)  # dia errado
    _, d2_usd, d2_ch = acc.delta_para_persistir()
    assert d2_ch == d_ch  # delta intacto — nada foi confirmado
    assert d2_usd == pytest.approx(d_usd, rel=1e-3)


# --- _price_for: cobertura de prefixos e direcao ---


def test_calcular_custo_sonnet_usa_default_exato():
    # Garante o ramo "sonnet" do prefixo (entre fable e haiku).
    m = llm_metrics.calcular_custo("claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert m["cost_input_usd"] == 3.0
    assert m["cost_output_usd"] == 15.0
    assert m["cost_total_usd"] == 18.0


def test_override_preco_vazio_string_ignorado():
    # String vazia (apos strip) nao conta como override → cai no default.
    os.environ["ORGCONC_LLM_PRICE_HAIKU_IN"] = "   "
    m = llm_metrics.calcular_custo("claude-haiku-4-5", 1_000_000, 0)
    assert m["cost_input_usd"] == 1.0  # default haiku


def test_override_preco_sonnet_out_via_env():
    # Cobre direcao "output" no caminho de override (env var _OUT).
    os.environ["ORGCONC_LLM_PRICE_SONNET_OUT"] = "30.0"
    m = llm_metrics.calcular_custo("claude-sonnet-4-6", 0, 1_000_000)
    assert m["cost_output_usd"] == 30.0


def test_calcular_custo_arredonda_seis_casas():
    # 1 token de input em fable = 10/1M = 0.00001 → mantem 6 casas.
    m = llm_metrics.calcular_custo("claude-fable-5", 1, 0)
    assert m["cost_input_usd"] == 0.00001
    assert m["cost_total_usd"] == 0.00001


def test_calcular_custo_converte_tokens_para_int():
    # input/output como float devem ser normalizados para int no retorno.
    m = llm_metrics.calcular_custo("claude-haiku-4-5", 100.0, 50.0)
    assert m["input_tokens"] == 100
    assert m["output_tokens"] == 50
    assert isinstance(m["input_tokens"], int)
    assert isinstance(m["output_tokens"], int)


# --- _threshold_alerta: parsing e bordas ---


def test_threshold_alerta_default_zero_sem_env():
    assert llm_metrics._threshold_alerta() == 0.0


def test_threshold_alerta_valor_invalido_vira_zero():
    os.environ["ORGCONC_LLM_COST_ALERT_USD"] = "abc"
    assert llm_metrics._threshold_alerta() == 0.0


def test_threshold_alerta_negativo_eh_clampado_para_zero():
    os.environ["ORGCONC_LLM_COST_ALERT_USD"] = "-10"
    assert llm_metrics._threshold_alerta() == 0.0


def test_threshold_alerta_valor_valido():
    os.environ["ORGCONC_LLM_COST_ALERT_USD"] = "2.5"
    assert llm_metrics._threshold_alerta() == 2.5


# --- _AcumuladorDiario.snapshot ---


def test_snapshot_reflete_estado_atual():
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)  # 0.6
    dia, total, chamadas = llm_metrics._ACUMULADOR.snapshot()
    assert dia  # dia ISO nao vazio
    assert total == pytest.approx(0.6, rel=1e-3)
    assert chamadas == 1


def test_snapshot_acumulador_zerado():
    dia, total, chamadas = llm_metrics._ACUMULADOR.snapshot()
    # Acumulador recem-criado: dia vazio, zero custo, zero chamadas.
    assert dia == ""
    assert total == 0.0
    assert chamadas == 0


# --- registrar_uso: sem duracao_ms e telemetria opcional ---


def test_registrar_uso_sem_duracao_nao_inclui_campo(caplog):
    with caplog.at_level(logging.INFO, logger="orgconc.llm.metrics"):
        llm_metrics.registrar_uso("claude-haiku-4-5", "H", 1_000, 1_000)
    rec = next(r for r in caplog.records if r.message == "llm_uso")
    assert not hasattr(rec, "llm_duracao_ms")


def test_registrar_uso_prometheus_erro_e_silencioso(caplog, monkeypatch):
    # A exportacao Prometheus e best-effort: erro na lib opcional nao quebra.
    import api.core.prometheus_metrics as prom

    def _boom(*_a, **_k):
        raise RuntimeError("prometheus indisponivel")

    monkeypatch.setattr(prom, "registrar_llm_prometheus", _boom)
    with caplog.at_level(logging.INFO, logger="orgconc.llm.metrics"):
        metrics = llm_metrics.registrar_uso("claude-haiku-4-5", "H", 1_000, 1_000)
    # Mesmo com erro na telemetria, o calculo de custo e retornado normalmente.
    assert "cost_total_usd" in metrics
    assert "cost_dia_usd" in metrics


# --- persistir_custo_diario_async: UPSERT incremental (sem banco real) ---


def _fake_async_db() -> MagicMock:
    """AsyncSession mockada com execute/commit/rollback assincronos."""
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_persistir_sem_delta_retorna_false():
    # Nenhuma chamada registrada → delta_chamadas == 0 → pula persistencia.
    db = _fake_async_db()
    ok = await llm_metrics.persistir_custo_diario_async(db)
    assert ok is False
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_persistir_com_delta_executa_upsert_e_confirma():
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)  # 0.6
    db = _fake_async_db()
    ok = await llm_metrics.persistir_custo_diario_async(db)
    assert ok is True
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()
    # Apos commit, delta deve estar confirmado → nada mais a persistir.
    _, d_usd, d_ch = llm_metrics._ACUMULADOR.delta_para_persistir()
    assert d_ch == 0
    assert d_usd == pytest.approx(0.0, abs=1e-9)


@pytest.mark.asyncio
async def test_persistir_segunda_chamada_sem_novo_uso_retorna_false():
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)
    db = _fake_async_db()
    assert await llm_metrics.persistir_custo_diario_async(db) is True
    db2 = _fake_async_db()
    # Sem novo uso, o delta foi confirmado na 1a chamada → 2a pula.
    assert await llm_metrics.persistir_custo_diario_async(db2) is False
    db2.execute.assert_not_called()


@pytest.mark.asyncio
async def test_persistir_erro_no_execute_faz_rollback_e_nao_confirma(caplog):
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)  # 0.6
    db = _fake_async_db()
    db.execute = AsyncMock(side_effect=RuntimeError("db caiu"))
    with caplog.at_level(logging.ERROR, logger="orgconc.llm.metrics"):
        ok = await llm_metrics.persistir_custo_diario_async(db)
    assert ok is False
    db.rollback.assert_awaited_once()
    db.commit.assert_not_called()
    # Como nao houve commit, o delta NAO foi confirmado → sera retentado.
    _, d_usd, d_ch = llm_metrics._ACUMULADOR.delta_para_persistir()
    assert d_ch == 1
    assert d_usd == pytest.approx(0.6, rel=1e-3)


@pytest.mark.asyncio
async def test_persistir_erro_no_rollback_e_engolido(caplog):
    # Mesmo se o proprio rollback falhar, a funcao nao propaga excecao.
    llm_metrics.registrar_uso("claude-haiku-4-5", "H", 100_000, 100_000)
    db = _fake_async_db()
    db.execute = AsyncMock(side_effect=RuntimeError("commit falhou"))
    db.rollback = AsyncMock(side_effect=RuntimeError("rollback tambem falhou"))
    with caplog.at_level(logging.ERROR, logger="orgconc.llm.metrics"):
        ok = await llm_metrics.persistir_custo_diario_async(db)
    assert ok is False  # nao quebrou o request
