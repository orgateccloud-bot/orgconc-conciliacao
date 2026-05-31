"""Descoberta automatica do modelo Claude mais recente por familia.

Usa a Models API (GET /v1/models) para resolver opus/sonnet/haiku para o id
MAIS RECENTE disponivel na conta — assim novos modelos (ex.: Opus 4.8) entram
sem mudar codigo. Ha sempre um fallback hardcoded (DEFAULTS) para uso offline,
sem chave, ou quando ORGCONC_MODELS_AUTO=0.

A Anthropic NAO expoe precos por API; precos ficam em api/core/llm_metrics.py
(chaveados por familia: opus/sonnet/haiku), entao um id novo da mesma familia
ja e precificado corretamente.
"""
from __future__ import annotations

import logging

log = logging.getLogger("orgconc.models")

_FAMILIAS = ("opus", "sonnet", "haiku")

# Fallback offline — ultimo conhecido (atualizado 2026-05-31). Mantido em sincronia
# manual; em runtime, atualizar_modelos() sobrescreve com o que a API retornar.
DEFAULTS: dict[str, tuple[str, str]] = {
    "opus":   ("claude-opus-4-8", "Opus 4.8"),
    "sonnet": ("claude-sonnet-4-6", "Sonnet 4.6"),
    "haiku":  ("claude-haiku-4-5-20251001", "Haiku 4.5"),
}

# Emoji por familia para o modo multi-modelo.
EMOJI: dict[str, str] = {"opus": "🔵", "sonnet": "🟢", "haiku": "🟡"}


def descobrir_modelos(api_key: str, timeout_s: float = 5.0) -> dict[str, tuple[str, str]]:
    """Retorna {familia: (model_id, label)} com o modelo MAIS RECENTE de cada
    familia (por created_at), via Models API.

    Levanta excecao se a API falhar — o caller (config.atualizar_modelos) faz o
    fallback para DEFAULTS.
    """
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key, timeout=timeout_s)
    modelos = list(client.models.list(limit=100).data)

    resolvido: dict[str, tuple[str, str]] = {}
    for familia in _FAMILIAS:
        candidatos = [m for m in modelos if familia in m.id]
        if not candidatos:
            continue
        mais_novo = max(candidatos, key=lambda m: m.created_at)
        label = getattr(mais_novo, "display_name", None) or mais_novo.id
        resolvido[familia] = (mais_novo.id, label)
    return resolvido
