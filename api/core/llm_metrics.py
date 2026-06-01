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
from datetime import datetime, date as _date, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("orgconc.llm.metrics")

# Precos default (USD / 1M tokens) — pode ser sobrescrito por env.
# Atualizado p/ tabela oficial 2026 (claude.com/pricing#api):
# Opus 4.5+ caiu para $5/$25 (era $15/$75 no Opus 4/4.1). O projeto usa opus-4-7.
_DEFAULT_PRICES = {
    "opus": {"input": 5.0, "output": 25.0},
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
    """Acumula custo do dia (UTC) e dispara alerta unico acima do threshold.

    Rastreia tambem o quanto ja foi persistido no banco (``_persistido_*``) para
    permitir UPSERT *incremental* por delta. Isso e essencial com multiplos
    workers (uvicorn --workers N): cada processo tem seu proprio acumulador com
    apenas a SUA fatia do custo; persistir incrementalmente o delta soma as
    fatias no banco em vez de um worker sobrescrever o do outro.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._dia: str = ""
        self._total_usd: float = 0.0
        self._chamadas: int = 0
        self._alerta_disparado: bool = False
        # Marcadores do que ja foi gravado em llm_cost_daily (para delta).
        self._persistido_usd: float = 0.0
        self._persistido_chamadas: int = 0

    def _rolar_dia_se_preciso(self, hoje: str) -> None:
        """Zera o estado quando vira o dia (UTC). Chamar sob lock."""
        if hoje != self._dia:
            self._dia = hoje
            self._total_usd = 0.0
            self._chamadas = 0
            self._alerta_disparado = False
            self._persistido_usd = 0.0
            self._persistido_chamadas = 0

    def adicionar(self, custo_usd: float) -> tuple[float, bool]:
        """Soma o custo e retorna (total_dia_usd, atingiu_threshold_agora)."""
        hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        threshold = _threshold_alerta()
        with self._lock:
            self._rolar_dia_se_preciso(hoje)
            self._total_usd += custo_usd
            self._chamadas += 1
            atingiu = False
            if threshold > 0 and self._total_usd >= threshold and not self._alerta_disparado:
                self._alerta_disparado = True
                atingiu = True
            return self._total_usd, atingiu

    def snapshot(self) -> tuple[str, float, int]:
        """Retorna (dia_iso, total_usd, chamadas) atomicamente."""
        with self._lock:
            return self._dia, self._total_usd, self._chamadas

    def delta_para_persistir(self) -> tuple[str, float, int]:
        """Retorna (dia_iso, delta_usd, delta_chamadas) ainda nao gravado."""
        hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            self._rolar_dia_se_preciso(hoje)
            # max(0.0, ...) evita delta negativo por drift de arredondamento float.
            delta_usd = max(0.0, self._total_usd - self._persistido_usd)
            delta_chamadas = self._chamadas - self._persistido_chamadas
            return self._dia, round(delta_usd, 6), delta_chamadas

    def confirmar_persistido(self, dia: str, delta_usd: float, delta_chamadas: int) -> None:
        """Marca o delta como gravado — somente se ainda for o mesmo dia.

        Se o dia virou entre o peek e a confirmacao, o estado ja foi zerado e o
        delta antigo nao deve ser remarcado (a gravacao do dia anterior ja foi
        persistida corretamente; o novo dia comeca do zero).
        """
        with self._lock:
            if dia != self._dia:
                return
            self._persistido_usd += delta_usd
            self._persistido_chamadas += delta_chamadas


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
    # Exporta para Prometheus (best-effort — lib opcional, nunca quebra).
    try:
        from api.core.prometheus_metrics import registrar_llm_prometheus

        registrar_llm_prometheus(
            model_id,
            metrics["input_tokens"],
            metrics["output_tokens"],
            metrics["cost_total_usd"],
        )
    except Exception:  # noqa: BLE001 — telemetria opcional
        pass
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


async def persistir_custo_diario_async(db: "AsyncSession") -> bool:
    """UPSERT *incremental* do delta nao gravado na tabela llm_cost_daily.

    Best-effort: nunca propaga exceção — só loga. Pula se não há delta novo.
    Retorna True se persistiu, False caso contrário.

    Em conflito (dia já existe), SOMA o delta ao valor atual (não substitui).
    Isso mantém a contabilização correta com múltiplos workers, múltiplas
    persistências no mesmo dia e reinício do processo.
    """
    dia_iso, delta_usd, delta_chamadas = _ACUMULADOR.delta_para_persistir()
    if not dia_iso or delta_chamadas <= 0:
        return False
    committed = False
    try:
        from sqlalchemy.dialects.postgresql import insert as _pg_insert
        from api.db.models import LlmCostDaily

        dia_obj = _date.fromisoformat(dia_iso)
        valor = Decimal(str(round(delta_usd, 4)))

        stmt = _pg_insert(LlmCostDaily).values(
            dia=dia_obj,
            custo_usd=valor,
            chamadas=delta_chamadas,
            atualizado_em=datetime.now(timezone.utc),
        )
        # UPSERT atômico incremental — em conflito soma o delta ao acumulado.
        stmt = stmt.on_conflict_do_update(
            index_elements=["dia"],
            set_={
                "custo_usd": LlmCostDaily.custo_usd + stmt.excluded.custo_usd,
                "chamadas": LlmCostDaily.chamadas + stmt.excluded.chamadas,
                "atualizado_em": stmt.excluded.atualizado_em,
            },
        )
        await db.execute(stmt)
        await db.commit()
        committed = True
        return True
    except Exception:  # noqa: BLE001 — best-effort, não pode quebrar request
        log.exception("Falha persistindo custo diário (dia=%s, delta=%.4f)", dia_iso, delta_usd)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False
    finally:
        # Marca delta como gravado mesmo sob CancelledError (BaseException).
        # Se não houve commit, committed=False e o delta será retentado.
        if committed:
            _ACUMULADOR.confirmar_persistido(dia_iso, delta_usd, delta_chamadas)
