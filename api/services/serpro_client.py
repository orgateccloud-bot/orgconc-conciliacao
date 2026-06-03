"""Cliente do motor oficial SERPRO (Calculadora CBS/IBS) — Fase 1.

O OrgConc ORQUESTRA, não recalcula: este cliente chama o motor (hospedado ou
offline — mesmo contrato) via httpx, traduzindo IC-02 ↔ SERPRO em serpro_traducao.
O formato externo é PROVISÓRIO (sem OpenAPI oficial) — ver serpro_traducao.py.
"""
from __future__ import annotations

import logging

import httpx

from api.core import config
from api.schemas_cbs_ibs import ApuracaoCBSIBS, OperacaoFiscalInput
from api.services.calculadora_cbs_ibs import payload_hash_de
from api.services.serpro_traducao import (
    TraducaoSerproError,
    endpoint_para,
    ic02_para_serpro,
    serpro_para_ic02,
)

log = logging.getLogger("orgconc.cbs_ibs.serpro")


class CalculadoraIndisponivel(RuntimeError):
    """Falha ao obter apuração do motor SERPRO (rede, status ou formato).

    Erro TRATÁVEL: o endpoint /fiscal/apurar deve traduzir para 502/503, nunca
    deixar virar 500 — a indisponibilidade do motor não é um bug do OrgConc.
    """


def _construir_client() -> httpx.AsyncClient:
    """AsyncClient com base_url, timeout, mTLS e api-key conforme a config."""
    kwargs: dict = {
        "base_url": config.CALCULADORA_BASE_URL,
        "timeout": config.CALCULADORA_TIMEOUT_S,
    }
    if config.CALCULADORA_CERT and config.CALCULADORA_KEY:
        kwargs["cert"] = (config.CALCULADORA_CERT, config.CALCULADORA_KEY)  # mTLS
    if config.CALCULADORA_API_KEY:
        kwargs["headers"] = {"Authorization": f"Bearer {config.CALCULADORA_API_KEY}"}
    return httpx.AsyncClient(**kwargs)


async def apurar_via_serpro(
    inp: OperacaoFiscalInput, *, client: httpx.AsyncClient | None = None
) -> ApuracaoCBSIBS:
    """Apura CBS/IBS chamando o motor SERPRO. `client` injetável (testes).

    Levanta CalculadoraIndisponivel em qualquer falha de rede, status HTTP de
    erro ou resposta fora do formato esperado.
    """
    if not config.CALCULADORA_BASE_URL:
        raise CalculadoraIndisponivel(
            "CALCULADORA_BASE_URL não configurada (exigida nos modos hospedada/offline)."
        )
    rota = endpoint_para(inp)
    payload = ic02_para_serpro(inp)
    ph = payload_hash_de(inp)

    owns = client is None
    cli = client or _construir_client()
    try:
        resp = await cli.post(rota, json=payload)
        resp.raise_for_status()
        dados = resp.json()
    except httpx.HTTPStatusError as e:
        log.warning("SERPRO status %s em %s", e.response.status_code, rota)
        raise CalculadoraIndisponivel(
            f"motor SERPRO retornou HTTP {e.response.status_code}"
        ) from e
    except httpx.HTTPError as e:
        log.warning("SERPRO falha de comunicação: %s", type(e).__name__)
        raise CalculadoraIndisponivel(
            f"falha de comunicação com o motor SERPRO: {type(e).__name__}"
        ) from e
    finally:
        if owns:
            await cli.aclose()

    try:
        apur = serpro_para_ic02(dados, inp, ph)
    except TraducaoSerproError as e:
        log.warning("SERPRO resposta em formato inesperado: %s", e)
        raise CalculadoraIndisponivel(f"resposta do SERPRO em formato inesperado: {e}") from e

    log.info(
        "cbs_ibs.serpro: documento=%s rota=%s vTotTrib=%s",
        inp.documento_id, rota, apur.vTotTrib,
    )
    return apur
