"""Cliente HTTP do SERPRO (Calculadora de Tributos / RTC) — Fase 1, IC-02.

Implementa o que NÃO depende da spec específica da Calculadora:
  - autenticação OAuth2 client_credentials (Consumer Key/Secret -> Bearer token),
    com cache do token até perto de expirar;
  - transporte: POST autenticado ao endpoint da Calculadora (CALCULADORA_BASE_URL).

O mapeamento IC-02 <-> payload SERPRO (montar request e parsear response) fica em
`api/services/calculadora_cbs_ibs.py` como TODO até termos a spec oficial da API
(endpoint + schema), disponível na área do cliente cliente.serpro.gov.br.

Fluxo de auth (doc SERPRO, igual Integra Contador / Consulta CNPJ):
  POST {SERPRO_TOKEN_URL}  Authorization: Basic base64(key:secret)
       body: grant_type=client_credentials
  -> { "access_token": "...", "token_type": "Bearer", "expires_in": 3600 }
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Optional

import httpx

from api.core import config

log = logging.getLogger(__name__)

# Cache do token em processo: (access_token, expira_em_epoch). Renova com folga.
_token_cache: dict[str, Any] = {"access_token": None, "expira_em": 0.0}
_RENOVAR_ANTES_S = 60.0  # renova 60s antes de expirar

# Cache da versão da base do motor (GET /versao/status). TTL curto: a base muda
# raramente e não queremos um round-trip extra a cada apuração.
_versao_cache: dict[str, Any] = {"valor": None, "expira_em": 0.0}
_VERSAO_TTL_S = 300.0


class SerproConfigError(RuntimeError):
    """Credenciais/URL do SERPRO ausentes ou incompletas."""


def credenciais_ok() -> bool:
    """True se há Consumer Key + Secret configurados (não valida com a rede)."""
    return bool(config.SERPRO_CONSUMER_KEY and config.SERPRO_CONSUMER_SECRET)


def _basic_auth_header() -> str:
    raw = f"{config.SERPRO_CONSUMER_KEY}:{config.SERPRO_CONSUMER_SECRET}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


async def obter_token(*, forcar: bool = False) -> str:
    """Retorna um Bearer token válido (do cache ou renovando via SERPRO).

    Levanta SerproConfigError se faltarem credenciais; httpx.HTTPError em falha
    de rede/HTTP do endpoint de token.
    """
    if not credenciais_ok():
        raise SerproConfigError(
            "SERPRO_CONSUMER_KEY/SERPRO_CONSUMER_SECRET ausentes — configure as "
            "credenciais da área do cliente (cliente.serpro.gov.br)."
        )
    agora = time.time()
    if not forcar and _token_cache["access_token"] and _token_cache["expira_em"] > agora:
        return _token_cache["access_token"]

    async with httpx.AsyncClient(timeout=config.CALCULADORA_TIMEOUT_S) as cli:
        resp = await cli.post(
            config.SERPRO_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )
    resp.raise_for_status()
    body = resp.json()
    token = body["access_token"]
    expira_em_s = float(body.get("expires_in", 3600))
    _token_cache["access_token"] = token
    _token_cache["expira_em"] = agora + max(0.0, expira_em_s - _RENOVAR_ANTES_S)
    return token


async def chamar_calculadora(payload: dict, *, caminho: str = "") -> dict:
    """POST ao endpoint da Calculadora (CALCULADORA_BASE_URL[+caminho]).

    Genérico de transporte — recebe o payload (dict, já no formato SERPRO montado
    pelo caller) e devolve o JSON da resposta.

    Auth condicional: com Consumer Key/Secret (API hospedada SERPRO via gateway)
    usa Bearer + renova 1x em 401; SEM credenciais trata como instância ABERTA
    (calculadora offline local ou ambiente de teste) e chama sem Authorization.
    """
    base = config.CALCULADORA_BASE_URL
    if not base:
        raise SerproConfigError("CALCULADORA_BASE_URL ausente — defina o endpoint da Calculadora SERPRO.")
    url = base.rstrip("/") + (("/" + caminho.lstrip("/")) if caminho else "")
    autenticado = credenciais_ok()

    async def _post(token: Optional[str]) -> httpx.Response:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=config.CALCULADORA_TIMEOUT_S) as cli:
            return await cli.post(url, headers=headers, json=payload)

    resp = await _post(await obter_token() if autenticado else None)
    if autenticado and resp.status_code == 401:  # token expirado -> renova e tenta 1x
        resp = await _post(await obter_token(forcar=True))
    resp.raise_for_status()
    return resp.json()


async def obter_versao_db(*, forcar: bool = False) -> Optional[str]:
    """Consulta GET {CALCULADORA_BASE_URL}/versao/status e devolve a versaoDbLocal
    do motor (a base de regras RTC ativa) — ou None.

    Best-effort e cacheado (TTL curto): devolve None se não houver URL ou se a
    consulta falhar (rede, 404 no gateway hospedado, JSON inesperado). NUNCA
    levanta — é um pre-flight de diagnóstico, não pode bloquear a apuração.
    Auth condicional, igual a chamar_calculadora (Bearer só se houver credenciais).
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
        if credenciais_ok():
            headers["Authorization"] = f"Bearer {await obter_token()}"
        async with httpx.AsyncClient(timeout=config.CALCULADORA_TIMEOUT_S) as cli:
            resp = await cli.get(url, headers=headers)
        resp.raise_for_status()
        versao = (resp.json() or {}).get("versaoDbLocal")
    except (httpx.HTTPError, ValueError, SerproConfigError) as e:
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


def _reset_token_cache() -> None:
    """Para testes: limpa o cache do token."""
    _token_cache["access_token"] = None
    _token_cache["expira_em"] = 0.0


def _reset_versao_cache() -> None:
    """Para testes: limpa o cache da versão da base."""
    _versao_cache["valor"] = None
    _versao_cache["expira_em"] = 0.0
