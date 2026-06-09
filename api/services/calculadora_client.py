"""Cliente HTTP da Calculadora oficial de Tributos (CBS/IBS — RTC, IC-02).

OrgConc ORQUESTRA a calculadora oficial (não recalcula). O alvo é a instância
aberta do Portal de Tributos sobre Bens e Serviços (consumo.tributos.gov.br) ou
uma calculadora offline local — ambas SEM autenticação. Por isso este cliente é
apenas transporte: POST/GET ao endpoint em `CALCULADORA_BASE_URL`.

O mapeamento IC-02 <-> payload RTC (montar request e parsear response) fica em
`api/services/calculadora_cbs_ibs.py`.

Nota histórica: a Fase 1 chegou a ter auth OAuth2 (Consumer Key/Secret -> Bearer)
para o gateway SERPRO; o SERPRO foi excluído como alvo (2026-06-09) e a auth foi
removida — o transporte genérico já serve a instância aberta oficial.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from api.core import config

log = logging.getLogger(__name__)

# Cache da versão da base do motor (GET /versao/status). TTL curto: a base muda
# raramente e não queremos um round-trip extra a cada apuração.
_versao_cache: dict[str, Any] = {"valor": None, "expira_em": 0.0}
_VERSAO_TTL_S = 300.0


class CalculadoraConfigError(RuntimeError):
    """URL da Calculadora (CALCULADORA_BASE_URL) ausente ou inválida."""


async def chamar_calculadora(payload: dict, *, caminho: str = "") -> dict:
    """POST ao endpoint da Calculadora (CALCULADORA_BASE_URL[+caminho]).

    Genérico de transporte — recebe o payload (dict, já no formato RTC montado
    pelo caller) e devolve o JSON da resposta. Instância aberta/offline: sem
    autenticação. Levanta CalculadoraConfigError se faltar a URL.
    """
    base = config.CALCULADORA_BASE_URL
    if not base:
        raise CalculadoraConfigError(
            "CALCULADORA_BASE_URL ausente — defina o endpoint da Calculadora "
            "oficial (ex.: instância aberta consumo.tributos.gov.br ou offline local)."
        )
    url = base.rstrip("/") + (("/" + caminho.lstrip("/")) if caminho else "")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=config.CALCULADORA_TIMEOUT_S) as cli:
        resp = await cli.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()


async def obter_versao_db(*, forcar: bool = False) -> Optional[str]:
    """Consulta GET {CALCULADORA_BASE_URL}/versao/status e devolve a versaoDbLocal
    do motor (a base de regras RTC ativa) — ou None.

    Best-effort e cacheado (TTL curto): devolve None se não houver URL ou se a
    consulta falhar (rede, 404, JSON inesperado). NUNCA levanta — é um pre-flight
    de diagnóstico, não pode bloquear a apuração.
    """
    base = config.CALCULADORA_BASE_URL
    if not base:
        return None
    agora = time.time()
    if not forcar and _versao_cache["valor"] and _versao_cache["expira_em"] > agora:
        return _versao_cache["valor"]

    url = base.rstrip("/") + "/versao/status"
    headers = {"Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=config.CALCULADORA_TIMEOUT_S) as cli:
            resp = await cli.get(url, headers=headers)
        resp.raise_for_status()
        versao = (resp.json() or {}).get("versaoDbLocal")
    except (httpx.HTTPError, ValueError) as e:
        log.debug("Pre-flight de versão CBS/IBS indisponível (%s): %s", url, e)
        return None

    if versao:
        _versao_cache["valor"] = versao
        _versao_cache["expira_em"] = agora + _VERSAO_TTL_S
    return versao


async def checar_versao_base() -> Optional[str]:
    """Pre-flight antes de apurar: compara CBS_IBS_VERSAO_BASE (configurada) com a
    versaoDbLocal que o motor reporta. Loga WARNING em caso de divergência.

    NÃO bloqueia: a apuração segue (e, se a versão configurada não existir no motor,
    falhará lá — mas com este aviso o operador entende a causa). Devolve a versão do
    motor (ou None se indisponível).
    """
    esperada = config.CBS_IBS_VERSAO_BASE
    do_motor = await obter_versao_db()
    if do_motor and esperada and do_motor != esperada:
        log.warning(
            "Versão da base CBS/IBS divergente: CBS_IBS_VERSAO_BASE=%s, mas o motor "
            "reporta versaoDbLocal=%s. A apuração enviará versao=%s e pode falhar ou "
            "divergir — ajuste CBS_IBS_VERSAO_BASE ou atualize a base do motor.",
            esperada, do_motor, esperada,
        )
    return do_motor


def _reset_versao_cache() -> None:
    """Para testes: limpa o cache da versão da base."""
    _versao_cache["valor"] = None
    _versao_cache["expira_em"] = 0.0
