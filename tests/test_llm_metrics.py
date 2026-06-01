"""Testes para api/core/llm_metrics.py — calculo de custo e acumulador diario."""
from __future__ import annotations

import logging
import os

import pytest

from api.core import llm_metrics


@pytest.fixture(autouse=True)
def _limpar_estado():
    llm_metrics.resetar_acumulador_para_testes()
    for var in [
        "ORGCONC_LLM_COST_ALERT_USD",
        "ORGCONC_LLM_PRICE_OPUS_IN", "ORGCONC_LLM_PRICE_OPUS_OUT",
        "ORGCONC_LLM_PRICE_SONNET_IN", "ORGCONC_LLM_PRICE_SONNET_OUT",
        "ORGCONC_LLM_PRICE_HAIKU_IN", "ORGCONC_LLM_PRICE_HAIKU_OUT",
    ]:
        os.environ.pop(var, None)
    yield
    llm_metrics.resetar_acumulador_para_testes()


def test_calcular_custo_opus_usa_default():
    m = llm_metrics.calcular_custo("claude-opus-4-7", 1_000_000, 1_000_000)
    # Opus 4.5+ = $5/$25 (tabela oficial 2026)
    assert m["cost_input_usd"] == 5.0
    assert m["cost_output_usd"] == 25.0
    assert m["cost_total_usd"] == 30.0
    assert m["model_id"] == "claude-opus-4-7"


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
    os.environ["ORGCONC_LLM_PRICE_OPUS_IN"] = "20.0"
    os.environ["ORGCONC_LLM_PRICE_OPUS_OUT"] = "100.0"
    m = llm_metrics.calcular_custo("claude-opus-4-7", 1_000_000, 1_000_000)
    assert m["cost_input_usd"] == 20.0
    assert m["cost_output_usd"] == 100.0


def test_override_preco_invalido_cai_em_default(caplog):
    os.environ["ORGCONC_LLM_PRICE_OPUS_IN"] = "nao-eh-numero"
    with caplog.at_level(logging.WARNING):
        m = llm_metrics.calcular_custo("claude-opus-4-7", 1_000_000, 0)
    assert m["cost_input_usd"] == 5.0


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
        llm_metrics.registrar_uso("claude-opus-4-7", "O", 1_000_000, 1_000_000)
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
