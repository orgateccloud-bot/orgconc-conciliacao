"""Chamadas async ao Claude e sintese multi-modelo."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time

from anthropic import Anthropic, APIStatusError, RateLimitError
from fastapi import HTTPException

from api.core.config import SYSTEM_PROMPT, _MODELOS_MULTI
from api.core.llm_metrics import registrar_uso

log = logging.getLogger("orgconc.llm")

# Retry config — exponential backoff em rate limit / 5xx
_MAX_RETRIES = 3
# Base do backoff em segundos: delay = _RETRY_BASE_DELAY ** tentativa (2s, 4s, 8s).
# Override via env (testes setam para 0 e evitam sleeps reais).
try:
    _RETRY_BASE_DELAY = float(os.environ.get("ORGCONC_LLM_RETRY_BASE_DELAY", "2"))
except ValueError:
    _RETRY_BASE_DELAY = 2.0

# Timeout de parede por chamada a um modelo. Override via env. Default 240s
# (extratos grandes + Sonnet/Opus podem passar de 90s).
try:
    _LLM_TIMEOUT_S = float(os.environ.get("ORGCONC_LLM_TIMEOUT_S", "240"))
except ValueError:
    _LLM_TIMEOUT_S = 240.0


def _get_client(api_key: str) -> Anthropic:
    """Fabrica do client Anthropic. Indirecao para facilitar mock em testes."""
    return Anthropic(api_key=api_key)


def _status_de_erro(exc: Exception) -> int | None:
    """Extrai o HTTP status code de um erro da API Anthropic, se houver."""
    return getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )


def _is_retriable(exc: Exception) -> bool:
    """Retry só em RateLimitError ou APIStatusError com status 5xx."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
        return isinstance(status, int) and 500 <= status < 600
    return False


async def chamar_modelo_async(
    api_key: str,
    prompt: str,
    model_id: str,
    label: str,
    max_tokens: int,
) -> dict:
    loop = asyncio.get_running_loop()

    def _call():
        c = _get_client(api_key)
        # Streaming: remove o limite de 10 min do SDK em respostas longas
        # (max_tokens alto) e evita o ValueError "Streaming is required".
        with c.messages.stream(
            model=model_id,
            max_tokens=max_tokens,
            # cache_control ephemeral economiza tokens em chamadas repetidas (system prompt fixo)
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            resp = stream.get_final_message()
        return {
            "texto": "\n".join(b.text for b in resp.content if b.type == "text"),
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "stop_reason": resp.stop_reason,
        }

    inicio = time.perf_counter()
    res: dict | None = None
    ultimo_erro: Exception | None = None

    for tentativa in range(1, _MAX_RETRIES + 1):
        try:
            res = await asyncio.wait_for(loop.run_in_executor(None, _call), timeout=_LLM_TIMEOUT_S)
            res["erro"] = None
            res["truncado"] = res.get("stop_reason") == "max_tokens"
            if res["truncado"]:
                log.warning(
                    "Resposta de %s TRUNCADA em max_tokens=%d — relatorio incompleto",
                    model_id, max_tokens,
                )
            break
        except asyncio.TimeoutError:
            log.warning("Timeout (%.0fs) chamando modelo %s", _LLM_TIMEOUT_S, model_id)
            res = {
                "texto": "", "input_tokens": 0, "output_tokens": 0,
                "erro": f"Timeout na API Claude ({_LLM_TIMEOUT_S:.0f}s)",
            }
            break
        except (RateLimitError, APIStatusError) as e:
            ultimo_erro = e
            if _is_retriable(e) and tentativa < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY ** tentativa  # 2s, 4s, 8s
                log.warning(
                    "Retry %d/%d em %s após %s (delay=%.1fs)",
                    tentativa, _MAX_RETRIES, model_id, type(e).__name__, delay,
                )
                if delay > 0:
                    await asyncio.sleep(delay)
                continue
            body = getattr(e, "body", None) or {}
            msg = (body.get("error") or {}).get("message") or str(e)
            log.warning("Erro no modelo %s: %s", model_id, msg)
            res = {
                "texto": "", "input_tokens": 0, "output_tokens": 0,
                "erro": msg, "status_code": _status_de_erro(e),
            }
            break
        except Exception as e:
            # Defensivo: qualquer erro inesperado (ex.: ValueError do SDK) vira
            # erro amigavel em vez de vazar como 500.
            log.warning("Erro inesperado em %s: %s", model_id, e)
            res = {
                "texto": "", "input_tokens": 0, "output_tokens": 0,
                "erro": f"{type(e).__name__}: {e}",
            }
            break

    if res is None:  # defensivo — não deve ocorrer
        msg = str(ultimo_erro) if ultimo_erro else "Falha desconhecida"
        res = {"texto": "", "input_tokens": 0, "output_tokens": 0, "erro": msg}

    dur_ms = (time.perf_counter() - inicio) * 1000

    if not res.get("erro") and (res.get("input_tokens") or res.get("output_tokens")):
        try:
            metrics = registrar_uso(
                model_id=model_id,
                label=label,
                input_tokens=res.get("input_tokens", 0),
                output_tokens=res.get("output_tokens", 0),
                duracao_ms=dur_ms,
            )
            res["cost_usd"] = metrics["cost_total_usd"]
            res["cost_dia_usd"] = metrics["cost_dia_usd"]
        except Exception:  # noqa: BLE001 — fallback de telemetria nao deve quebrar response
            log.exception("Falha registrando metrica LLM para %s", model_id)

    res.update({"modelo": model_id, "label": label})
    return res


async def sintetizar_consenso(
    api_key: str,
    resultados: list[dict],
    max_tokens: int,
) -> tuple[str, float]:
    validos = [r for r in resultados if not r.get("erro") and r["texto"]]
    if not validos:
        return "Nenhum modelo produziu resultado valido.", 0.0
    if len(validos) == 1:
        return validos[0]["texto"], 0.5

    secoes = "\n\n".join(f"### Análise — {r['label']}\n{r['texto']}" for r in validos)
    prompt_juiz = (
        f"Você recebeu {len(validos)} análises independentes do mesmo extrato bancário, "
        "geradas por modelos Claude diferentes. Produza um RELATÓRIO FINAL consolidado em Markdown:\n\n"
        "1. Primeira linha: `## Índice de Consenso: XX/100`\n"
        "2. Achados confirmados por >= 2 modelos\n"
        "3. Pontos divergentes\n"
        "4. Resumo Executivo · Anomalias · Classificações · Plano de Ação\n\n"
        f"---\n\n{secoes}"
    )
    res = await chamar_modelo_async(api_key, prompt_juiz, "claude-sonnet-4-6", "Síntese", max_tokens)
    texto = res["texto"] or validos[0]["texto"]
    m = re.search(r"[Íi]ndice\s+de\s+[Cc]onsenso[:\s]+(\d+)", texto)
    score = int(m.group(1)) / 100.0 if m else (len(validos) / 3 * 0.8)
    return texto, round(min(max(score, 0.0), 1.0), 3)


def get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY") or ""
    if not key:
        raise HTTPException(500, "ANTHROPIC_API_KEY nao configurada no servidor")
    return key


def friendly_anthropic_error(msg: str) -> str:
    if "credit balance" in msg.lower():
        return (
            "Saldo de creditos Anthropic esgotado. "
            "Recarregue em https://platform.claude.com/settings/billing "
            "ou use ?simular=true."
        )
    if "rate" in msg.lower() and "limit" in msg.lower():
        return "Rate limit da Anthropic atingido. Aguarde alguns segundos."
    return msg
