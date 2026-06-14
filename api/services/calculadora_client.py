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


class CalculadoraIndisponivel(RuntimeError):
    """A Calculadora oficial falhou de forma transitória/externa: HTTP 4xx/5xx,
    timeout, erro de conexão ou resposta não-JSON/malformada.

    Erro de DOMÍNIO (não vaza traceback): o router deve mapeá-lo para 502/503 com
    mensagem limpa. `status_http` traz o status retornado pela Calculadora quando
    houver (HTTPStatusError); None p/ timeout/conexão/JSON inválido.
    """

    def __init__(self, mensagem: str, *, status_http: Optional[int] = None) -> None:
        super().__init__(mensagem)
        self.status_http = status_http


async def chamar_calculadora(payload: dict, *, caminho: str = "") -> dict:
    """POST ao endpoint da Calculadora (CALCULADORA_BASE_URL[+caminho]).

    Genérico de transporte — recebe o payload (dict, já no formato RTC montado
    pelo caller) e devolve o JSON da resposta. Instância aberta/offline: sem
    autenticação.

    Levanta:
    - CalculadoraConfigError se faltar a URL (erro de configuração, não transitório).
    - CalculadoraIndisponivel se a Calculadora retornar HTTP de erro, estourar
      timeout, falhar a conexão ou devolver corpo não-JSON/não-objeto. Blinda o
      caminho de erro para que o router responda 502/503 sem vazar traceback (em
      vez de um 500 cru de httpx/json em produção).
    """
    base = config.CALCULADORA_BASE_URL
    if not base:
        raise CalculadoraConfigError(
            "CALCULADORA_BASE_URL ausente — defina o endpoint da Calculadora "
            "oficial (ex.: instância aberta consumo.tributos.gov.br ou offline local)."
        )
    url = base.rstrip("/") + (("/" + caminho.lstrip("/")) if caminho else "")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=config.CALCULADORA_TIMEOUT_S) as cli:
            resp = await cli.post(url, headers=headers, json=payload)
        resp.raise_for_status()
    except httpx.TimeoutException as e:
        log.warning("Calculadora CBS/IBS: timeout em %s (%ss): %s",
                    url, config.CALCULADORA_TIMEOUT_S, e)
        raise CalculadoraIndisponivel(
            "A Calculadora oficial (CBS/IBS) não respondeu no tempo limite. "
            "Tente novamente em instantes."
        ) from e
    except httpx.HTTPStatusError as e:
        sc = e.response.status_code
        log.warning("Calculadora CBS/IBS: HTTP %s em %s: %s", sc, url, e)
        raise CalculadoraIndisponivel(
            f"A Calculadora oficial (CBS/IBS) retornou erro HTTP {sc}.",
            status_http=sc,
        ) from e
    except httpx.HTTPError as e:
        # RequestError e demais erros de transporte (conexão, DNS, TLS...).
        log.warning("Calculadora CBS/IBS: falha de transporte em %s (%s): %s",
                    url, type(e).__name__, e)
        raise CalculadoraIndisponivel(
            "Não foi possível contatar a Calculadora oficial (CBS/IBS)."
        ) from e

    try:
        dados = resp.json()
    except ValueError as e:
        log.warning("Calculadora CBS/IBS: resposta não-JSON em %s: %s", url, e)
        raise CalculadoraIndisponivel(
            "A Calculadora oficial (CBS/IBS) devolveu uma resposta malformada (não-JSON)."
        ) from e
    if not isinstance(dados, dict):
        log.warning("Calculadora CBS/IBS: JSON inesperado em %s (tipo %s, esperado objeto)",
                    url, type(dados).__name__)
        raise CalculadoraIndisponivel(
            "A Calculadora oficial (CBS/IBS) devolveu um JSON inesperado (não é objeto)."
        )
    return dados


async def obter_versao_db(*, forcar: bool = False) -> Optional[str]:
    """Versão da base de regras RTC ativa no motor — ou None.

    Caminho oficial (verificado live na instância de produção, 2026-06-10):
    GET {base}/calculadora/dados-abertos/versao → campo `versaoDb` (ex.: V0033).
    Fallback p/ o legado GET /versao/status → `versaoDbLocal` (instâncias
    offline antigas). Best-effort e cacheado (TTL curto): devolve None se não
    houver URL ou se a consulta falhar — pre-flight de diagnóstico, nunca
    bloqueia a apuração.
    """
    base = config.CALCULADORA_BASE_URL
    if not base:
        return None
    agora = time.time()
    if not forcar and _versao_cache["valor"] and _versao_cache["expira_em"] > agora:
        return _versao_cache["valor"]

    headers = {"Accept": "application/json"}
    versao = None
    for caminho, campo in (("/calculadora/dados-abertos/versao", "versaoDb"),
                           ("/versao/status", "versaoDbLocal")):
        url = base.rstrip("/") + caminho
        try:
            async with httpx.AsyncClient(timeout=config.CALCULADORA_TIMEOUT_S) as cli:
                resp = await cli.get(url, headers=headers)
            resp.raise_for_status()
            versao = (resp.json() or {}).get(campo)
        except (httpx.HTTPError, ValueError) as e:
            log.debug("Pre-flight de versão CBS/IBS indisponível (%s): %s", url, e)
            continue
        if versao:
            break

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
