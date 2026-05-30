"""Integracao com o cliente SERPRO (consulta CPF/CNPJ).

Este modulo NAO contem o cliente em si — o cliente vive fora do repo em
`D:\\integracoes\\serpro\\serpro_client.py` (ou no path indicado por
ORGCONC_SERPRO_CLIENT_PATH). Aqui ficam apenas:

- Singleton lazy do SerproClient (uma instancia por processo).
- Bridge do audit_hook para o `logging_estruturado` (log JSON com request_id).
- Wrappers async (`consultar_cpf_async`, `consultar_cnpj_async`) via
  `asyncio.to_thread` — o cliente subjacente eh sincrono e a chamada de rede
  bloquearia o event loop do FastAPI.
- Tradutor de excecoes do cliente para `HTTPException` com status apropriado,
  para uso direto em endpoints FastAPI.

Variaveis de ambiente:

  ORGCONC_SERPRO_CLIENT_PATH   default "D:\\integracoes\\serpro" — pasta com
                               o arquivo serpro_client.py. Injetada em sys.path.
  ORGCONC_SERPRO_CONSUMER_KEY  credencial OAuth2 (modo producao).
  ORGCONC_SERPRO_CONSUMER_SECRET  credencial OAuth2 (modo producao).
  ORGCONC_SERPRO_DEMO_TOKEN    bearer fixo (modo demonstracao, mutuamente
                               exclusivo com KEY/SECRET).
  ORGCONC_SERPRO_AUDIT_SALT    pepper persistente para o hash de correlacao.
                               OBRIGATORIO em producao (sem ele, logs sao
                               vulneraveis a rainbow-table de CPFs).
  ORGCONC_SERPRO_BASE_URL      default "https://gateway.apiserpro.serpro.gov.br".
  ORGCONC_SERPRO_CPF_PATH      override do path padrao do CPF.
  ORGCONC_SERPRO_CNPJ_PATH     override do path padrao do CNPJ.
  ORGCONC_SERPRO_CERT_FILE     caminho do .crt do e-CNPJ (mTLS, opcional).
  ORGCONC_SERPRO_KEY_FILE      caminho do .key do e-CNPJ (mTLS, opcional).
  ORGCONC_SERPRO_TIMEOUT_S     default 15.

Quando KEY/SECRET e DEMO_TOKEN estiverem ambos ausentes, `obter_client()`
levanta SerproIntegrationError e os endpoints respondem 503 — o servidor
sobe normalmente, so os endpoints de SERPRO ficam desabilitados.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

log = logging.getLogger("orgconc.serpro")


# ── Erros desta camada ─────────────────────────────────────────────────────

class SerproIntegrationError(RuntimeError):
    """Falha de integracao (path errado, credenciais ausentes, etc)."""


# ── Carga lazy do cliente externo ──────────────────────────────────────────

_lock = threading.Lock()
_client: Optional[Any] = None       # SerproClient quando carregado
_exc_module: Optional[Any] = None    # modulo serpro_client (para excecoes)


def _resolver_caminho_cliente() -> Path:
    raw = os.environ.get("ORGCONC_SERPRO_CLIENT_PATH", r"D:\integracoes\serpro").strip()
    path = Path(raw)
    if not path.is_dir():
        raise SerproIntegrationError(
            f"ORGCONC_SERPRO_CLIENT_PATH aponta para diretorio inexistente: {path}. "
            "Ajuste no .env ou crie a pasta com serpro_client.py."
        )
    if not (path / "serpro_client.py").is_file():
        raise SerproIntegrationError(
            f"serpro_client.py nao encontrado em {path}. "
            "Verifique ORGCONC_SERPRO_CLIENT_PATH."
        )
    return path


def _carregar_modulo_serpro():
    """Importa serpro_client (modulo externo) injetando em sys.path."""
    global _exc_module
    if _exc_module is not None:
        return _exc_module
    pasta = _resolver_caminho_cliente()
    pasta_str = str(pasta)
    if pasta_str not in sys.path:
        sys.path.insert(0, pasta_str)
    import serpro_client  # noqa: E402  (import dinamico controlado)
    _exc_module = serpro_client
    return serpro_client


def _construir_client():
    _exigir_audit_salt_producao()
    mod = _carregar_modulo_serpro()

    key = os.environ.get("ORGCONC_SERPRO_CONSUMER_KEY", "").strip() or None
    secret = os.environ.get("ORGCONC_SERPRO_CONSUMER_SECRET", "").strip() or None
    demo = os.environ.get("ORGCONC_SERPRO_DEMO_TOKEN", "").strip() or None
    salt = os.environ.get("ORGCONC_SERPRO_AUDIT_SALT", "").strip() or None
    base_url = os.environ.get("ORGCONC_SERPRO_BASE_URL", "").strip() or None
    cpf_path = os.environ.get("ORGCONC_SERPRO_CPF_PATH", "").strip() or None
    cnpj_path = os.environ.get("ORGCONC_SERPRO_CNPJ_PATH", "").strip() or None
    cert_file = os.environ.get("ORGCONC_SERPRO_CERT_FILE", "").strip() or None
    key_file = os.environ.get("ORGCONC_SERPRO_KEY_FILE", "").strip() or None
    timeout_s = float(os.environ.get("ORGCONC_SERPRO_TIMEOUT_S", "15") or "15")

    if not (key and secret) and not demo:
        raise SerproIntegrationError(
            "Credenciais SERPRO ausentes. Defina ORGCONC_SERPRO_CONSUMER_KEY + "
            "ORGCONC_SERPRO_CONSUMER_SECRET (producao) ou ORGCONC_SERPRO_DEMO_TOKEN "
            "(demonstracao) no .env."
        )

    client_cert: Optional[tuple[str, str]] = None
    if cert_file and key_file:
        client_cert = (cert_file, key_file)

    kwargs: dict[str, Any] = {
        "audit_hook": _audit_hook_estruturado,
        "audit_salt": salt,
        "timeout": timeout_s,
    }
    if key and secret:
        kwargs["consumer_key"] = key
        kwargs["consumer_secret"] = secret
    if demo:
        kwargs["demo_bearer_token"] = demo
    if base_url:
        kwargs["base_url"] = base_url
    if cpf_path:
        kwargs["cpf_path"] = cpf_path
    if cnpj_path:
        kwargs["cnpj_path"] = cnpj_path
    if client_cert:
        kwargs["client_cert"] = client_cert

    return mod.SerproClient(**kwargs)


def obter_client():
    """Retorna o singleton de SerproClient. Cria sob demanda, com lock."""
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is None:
            _client = _construir_client()
    return _client


def disponivel() -> bool:
    """True se ha credenciais minimas configuradas (sem instanciar o cliente)."""
    key = os.environ.get("ORGCONC_SERPRO_CONSUMER_KEY", "").strip()
    secret = os.environ.get("ORGCONC_SERPRO_CONSUMER_SECRET", "").strip()
    demo = os.environ.get("ORGCONC_SERPRO_DEMO_TOKEN", "").strip()
    return bool((key and secret) or demo)


def _exigir_audit_salt_producao() -> None:
    env = os.environ.get("ORGCONC_ENV", "development").strip().lower()
    if env not in ("production", "prod"):
        return
    if not os.environ.get("ORGCONC_SERPRO_AUDIT_SALT", "").strip():
        raise SerproIntegrationError(
            "ORGCONC_SERPRO_AUDIT_SALT e obrigatorio em producao para consultas SERPRO."
        )


# ── Bridge do audit_hook -> logging estruturado ────────────────────────────

def _audit_hook_estruturado(evento: dict[str, Any]) -> None:
    """Recebe o dict de auditoria do cliente e re-emite via log JSON.

    Como o cliente ja mascara o documento e adiciona o hash de correlacao,
    aqui so propagamos os campos para o `logging_estruturado` (que adiciona
    request_id, timestamp ISO etc).
    """
    extras = {
        "audit_event": evento.get("evento"),
        "tipo_consulta": evento.get("tipo"),
        "documento_mascarado": evento.get("documento_mascarado"),
        "documento_hash": evento.get("documento_hash"),
        "resultado": evento.get("resultado"),
    }
    log.info("serpro_consulta_audit", extra={k: v for k, v in extras.items() if v is not None})


# ── Tradutor de excecoes do cliente -> HTTPException ───────────────────────

def _mapear_excecao_para_http(exc: Exception) -> HTTPException:
    """Mapeia excecoes do serpro_client para HTTPException.

    Status escolhidos:
      400 documento invalido (validacao local de DV)
      404 nao encontrado na base da Receita
      451 menor de idade (Unavailable For Legal Reasons — LGPD)
      429 cota excedida
      502 falha de auth no gateway / erro generico do SERPRO
      503 cliente desconfigurado / dependencia indisponivel
      504 falha de rede / timeout
    """
    mod = _exc_module
    if mod is None:
        # Sem modulo carregado, classifica pela hierarquia genérica.
        return HTTPException(status_code=502, detail=f"Erro SERPRO: {type(exc).__name__}")

    if isinstance(exc, mod.SerproDocumentoInvalido):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, mod.SerproNaoEncontrado):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, mod.SerproMenorDeIdade):
        # 451 Unavailable For Legal Reasons — sinal explicito de bloqueio legal.
        return HTTPException(
            status_code=451,
            detail="Dados bloqueados por se tratar de menor de idade (LGPD).",
        )
    if isinstance(exc, mod.SerproRateLimitError):
        return HTTPException(status_code=429, detail="Cota de consultas SERPRO excedida.")
    if isinstance(exc, mod.SerproNetworkError):
        return HTTPException(status_code=504, detail="Falha de rede ao consultar o SERPRO.")
    if isinstance(exc, mod.SerproAuthError):
        return HTTPException(status_code=502, detail="Falha de autenticacao no gateway SERPRO.")
    if isinstance(exc, mod.SerproConfigError):
        return HTTPException(status_code=503, detail="Integracao SERPRO desconfigurada.")
    if isinstance(exc, mod.SerproError):
        return HTTPException(status_code=502, detail=f"Erro SERPRO: {exc}")
    # Excecao fora do dominio: nao expoe detalhes.
    return HTTPException(status_code=500, detail="Erro interno na integracao SERPRO.")


# ── API async para os endpoints ────────────────────────────────────────────

async def consultar_cpf_async(cpf: str) -> dict[str, Any]:
    """Consulta CPF de forma nao-bloqueante. Levanta HTTPException em falha."""
    try:
        client = obter_client()
    except SerproIntegrationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

    def _executar():
        return client.consultar_cpf(cpf)

    try:
        resultado = await asyncio.to_thread(_executar)
    except Exception as exc:  # serpro_client levanta SerproError ou subclasses
        raise _mapear_excecao_para_http(exc) from None

    return _serializar_resultado(resultado)


async def consultar_cnpj_async(cnpj: str) -> dict[str, Any]:
    """Consulta CNPJ de forma nao-bloqueante. Levanta HTTPException em falha."""
    try:
        client = obter_client()
    except SerproIntegrationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

    def _executar():
        return client.consultar_cnpj(cnpj)

    try:
        resultado = await asyncio.to_thread(_executar)
    except Exception as exc:
        raise _mapear_excecao_para_http(exc) from None

    return _serializar_resultado(resultado)


def _serializar_resultado(resultado: Any) -> dict[str, Any]:
    """Converte ResultadoConsulta -> dict JSON-friendly.

    Preserva a flag `parcial` (HTTP 206 do SERPRO) e o `documento_mascarado`
    para que o caller saiba que aquele resultado nao deve ser logado cru.
    """
    return {
        "tipo": resultado.tipo,
        "documento_mascarado": resultado.documento_mascarado,
        "parcial": resultado.parcial,
        "dados": resultado.dados,
    }


# ── Reset (para testes) ────────────────────────────────────────────────────

def _resetar_singleton_para_testes() -> None:
    """Limpa o singleton — uso restrito a testes que reconfiguram env vars."""
    global _client, _exc_module
    with _lock:
        if _client is not None:
            try:
                _client.fechar()
            except Exception:
                pass
        _client = None
        _exc_module = None
