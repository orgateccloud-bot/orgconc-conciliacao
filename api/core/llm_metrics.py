"""Medicao de custo LLM (Anthropic Claude) por chamada.

Calcula custo em USD a partir de input/output tokens e logga estruturado.
Permite alerta acima de threshold diario via ORGCONC_LLM_COST_ALERT_USD.

Tabela de precos baseada em Anthropic (USD por 1M tokens). Override via env:
    ORGCONC_LLM_PRICE_<MODEL>_IN / _OUT  (ex: ORGCONC_LLM_PRICE_OPUS_IN=18.0)

A tabela usa "prefixo do model_id" como chave: opus / sonnet / haiku.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("orgconc.llm.metrics")

# Precos default (USD / 1M tokens) — pode ser sobrescrito por env
_DEFAULT_PRICES = {
    "opus": {"input": 15.0, "output": 75.0},
    "sonnet": {"input": 3.0, "output": 15.0},
    "haiku": {"input": 1.0, "output": 5.0},
}


_ENV_DIRECTION = {"input": "IN", "output": "OUT"}


def _price_for(model_id: str, direction: str) -> float:
    """Retorna USD/1M tokens para o modelo e direcao (input|output)."""
    key = "opus" if "opus" in model_id else "sonnet" if "sonnet" in model_id else "haiku"
    env_var = f"ORGCONC_LLM_PRICE_{key.upper()}_{_ENV_DIRECTION[direction]}"
    override = os.environ.get(env_var, "").strip()
    if override:
        try:
            return float(override)
        except ValueError:
            log.warning("Valor invalido em %s: %s — usando default", env_var, override)
    return _DEFAULT_PRICES[key][direction]


def calcular_custo(model_id: str, input_tokens: int, output_tokens: int) -> dict:
    """Calcula custo em USD para uma chamada LLM."""
    p_in = _price_for(model_id, "input")
    p_out = _price_for(model_id, "output")
    cost_in = (input_tokens / 1_000_000) * p_in
    cost_out = (output_tokens / 1_000_000) * p_out
    total = cost_in + cost_out
    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "cost_input_usd": round(cost_in, 6),
        "cost_output_usd": round(cost_out, 6),
        "cost_total_usd": round(total, 6),
        "model_id": model_id,
    }


class _AcumuladorDiario:
    """Acumula custo do dia (UTC) e dispara alerta unico acima do threshold."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._dia: str = ""
        self._total_usd: float = 0.0
        self._alerta_disparado: bool = False

    def adicionar(self, custo_usd: float) -> tuple[float, bool]:
        """Soma o custo e retorna (total_dia_usd, atingiu_threshold_agora)."""
        hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        threshold = _threshold_alerta()
        with self._lock:
            if hoje != self._dia:
                self._dia = hoje
                self._total_usd = 0.0
                self._alerta_disparado = False
            self._total_usd += custo_usd
            atingiu = False
            if threshold > 0 and self._total_usd >= threshold and not self._alerta_disparado:
                self._alerta_disparado = True
                atingiu = True
            return self._total_usd, atingiu


def _threshold_alerta() -> float:
    raw = os.environ.get("ORGCONC_LLM_COST_ALERT_USD", "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


_ACUMULADOR = _AcumuladorDiario()


def registrar_uso(
    model_id: str,
    label: str,
    input_tokens: int,
    output_tokens: int,
    duracao_ms: Optional[float] = None,
) -> dict:
    """Calcula custo, logga estruturado e checa threshold diario."""
    metrics = calcular_custo(model_id, input_tokens, output_tokens)
    total_dia, atingiu = _ACUMULADOR.adicionar(metrics["cost_total_usd"])
    extra = {
        "llm_model": model_id,
        "llm_label": label,
        "llm_input_tokens": metrics["input_tokens"],
        "llm_output_tokens": metrics["output_tokens"],
        "llm_cost_total_usd": metrics["cost_total_usd"],
        "llm_cost_dia_usd": round(total_dia, 4),
    }
    if duracao_ms is not None:
        extra["llm_duracao_ms"] = round(duracao_ms, 1)
    log.info("llm_uso", extra=extra)
    if atingiu:
        log.warning(
            "llm_custo_threshold_atingido",
            extra={"llm_cost_dia_usd": round(total_dia, 4), "threshold_usd": _threshold_alerta()},
        )
    metrics["cost_dia_usd"] = round(total_dia, 4)
    return metrics


def resetar_acumulador_para_testes() -> None:
    """Util apenas em testes."""
    global _ACUMULADOR
    _ACUMULADOR = _AcumuladorDiario()
