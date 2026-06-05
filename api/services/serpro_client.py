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
import time
from typing import Any

import httpx

from api.core import config

# Cache do token em processo: (access_token, expira_em_epoch). Renova com folga.
_token_cache: dict[str, Any] = {"access_token": None, "expira_em": 0.0}
_RENOVAR_ANTES_S = 60.0  # renova 60s antes de expirar


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
    """POST autenticado ao endpoint da Calculadora (CALCULADORA_BASE_URL[+caminho]).

    Genérico de transporte — recebe o payload (dict, já no formato SERPRO montado
    pelo caller) e devolve o JSON da resposta. Renova o token 1x em 401.
    """
    base = config.CALCULADORA_BASE_URL
    if not base:
        raise SerproConfigError("CALCULADORA_BASE_URL ausente — defina o endpoint da Calculadora SERPRO.")
    url = base.rstrip("/") + (("/" + caminho.lstrip("/")) if caminho else "")

    async def _post(token: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=config.CALCULADORA_TIMEOUT_S) as cli:
            return await cli.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
            )

    resp = await _post(await obter_token())
    if resp.status_code == 401:  # token expirado/revogado -> renova e tenta 1x
        resp = await _post(await obter_token(forcar=True))
    resp.raise_for_status()
    return resp.json()


def _reset_token_cache() -> None:
    """Para testes: limpa o cache do token."""
    _token_cache["access_token"] = None
    _token_cache["expira_em"] = 0.0
