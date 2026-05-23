"""Chamadas async ao Claude e sintese multi-modelo."""
from __future__ import annotations

import asyncio
import logging
import os
import re

from anthropic import Anthropic, APIStatusError
from fastapi import HTTPException

from api.core.config import SYSTEM_PROMPT, _MODELOS_MULTI

log = logging.getLogger("orgconc.llm")


async def chamar_modelo_async(
    api_key: str,
    prompt: str,
    model_id: str,
    label: str,
    max_tokens: int,
) -> dict:
    loop = asyncio.get_event_loop()

    def _call():
        c = Anthropic(api_key=api_key)
        resp = c.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "texto": "\n".join(b.text for b in resp.content if b.type == "text"),
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }

    try:
        res = await loop.run_in_executor(None, _call)
    except APIStatusError as e:
        body = getattr(e, "body", None) or {}
        msg = (body.get("error") or {}).get("message") or str(e)
        log.warning("Erro no modelo %s: %s", model_id, msg)
        res = {"texto": "", "input_tokens": 0, "output_tokens": 0, "erro": msg}
    else:
        res["erro"] = None

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
