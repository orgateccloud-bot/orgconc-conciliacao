"""Autenticacao JWT para OrgConc.

Implementa:
- Hashing de senhas com bcrypt (direto, sem passlib)
- Geracao e validacao de JWT (HS256)
- Dependency FastAPI `current_user` com acesso anonimo em dev/staging

Modelo de revogacao de sessao:
- Refresh token (opaco, persistido): revogado server-side no logout
  (revogar_por_hash), logout-all e troca/reset de senha (revogar_todos_do_sub).
  Apresentar um refresh revogado -> 401 (buscar_ativo_por_hash filtra revogado_em).
- Access token (JWT, TTL curto ~120min): denylist por `jti` em Redis (#9). Ao
  fazer logout/logout-all e troca/reset de senha, o `jti` do access atual entra
  na denylist `revoked:{jti}` com TTL = tempo restante ate `exp` — assim a
  revogacao e instantanea (nao precisa esperar o TTL do token). `decodificar_token`
  consulta a denylist a cada request. Sem REDIS_URL (dev), a denylist degrada
  silenciosamente (log unico de aviso): nao quebra o fluxo, apenas perde a
  revogacao instantanea do access (o refresh revogavel + TTL curto continuam
  valendo). Fail-open de proposito: indisponibilidade do Redis nao pode derrubar
  toda a autenticacao.

Variaveis de ambiente:
- ORGCONC_JWT_SECRET    : chave de assinatura (>=32 chars). Se ausente, gera
                          uma random no startup (tokens nao sobrevivem restart)
- ORGCONC_JWT_TTL_MIN   : expiracao em minutos (default 120)
- REDIS_URL             : (opcional) store da denylist de access tokens por jti.
                          Ausente -> denylist desativada (degrada com aviso).
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets as _secrets
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

log = logging.getLogger("orgconc.auth")

# ── Bcrypt (direto, sem passlib) ──────────────────────────────────────────────
# passlib 1.7.4 (nao-mantido) quebra com bcrypt >= 5 (levanta ValueError na
# auto-deteccao do backend). Usamos bcrypt direto. Como o bcrypt usa no maximo
# 72 bytes da senha e o bcrypt >= 5 REJEITA entradas maiores (antes truncava),
# truncamos explicitamente a 72 bytes — preserva o comportamento anterior
# (truncate_error=False) e a compatibilidade com hashes ja armazenados.
_BCRYPT_MAX_BYTES = 72


def _senha_72(senha: str) -> bytes:
    return senha.encode("utf-8")[:_BCRYPT_MAX_BYTES]

# ── Config ──────────────────────────────────────────────────────────────────

# Ambiente: production rejeita JWT secret fraco/ausente e bloqueia anonimo
_ENV = os.environ.get("ORGCONC_ENV", "development").strip().lower()
_IS_PROD = _ENV in ("production", "prod")

_JWT_SECRET = os.environ.get("ORGCONC_JWT_SECRET", "").strip()
if not _JWT_SECRET:
    if _IS_PROD:
        raise RuntimeError(
            "ORGCONC_JWT_SECRET e OBRIGATORIO em producao (>= 32 chars). "
            "Gere com: openssl rand -hex 32"
        )
    _JWT_SECRET = _secrets.token_urlsafe(48)
    log.warning(
        "ORGCONC_JWT_SECRET nao configurado — gerei um aleatorio. "
        "Tokens nao sobreviverao restart. Configure no .env em producao."
    )
elif len(_JWT_SECRET) < 32:
    if _IS_PROD:
        raise RuntimeError(
            f"ORGCONC_JWT_SECRET fraco ({len(_JWT_SECRET)} chars). "
            "Em producao deve ter >= 32 chars. Gere com: openssl rand -hex 32"
        )
    log.warning("ORGCONC_JWT_SECRET tem menos de 32 chars — fraco. Aumente.")

_JWT_TTL_MIN = int(os.environ.get("ORGCONC_JWT_TTL_MIN", "120"))
_JWT_ALG = "HS256"

# Refresh tokens (opacos, sha256) — TTL em dias.
REFRESH_TTL_DAYS = int(os.environ.get("ORGCONC_REFRESH_TTL_DAYS", "30"))

# ── Denylist de access tokens por jti (#9) ────────────────────────────────────
# Revogacao instantanea do access token: ao deslogar/trocar senha, o `jti` do
# token atual entra na denylist `revoked:{jti}` em Redis com TTL = exp restante.
# decodificar_token consulta a denylist. Sem REDIS_URL, degrada (sem denylist):
# o access sobrevive ate o exp natural, mas o refresh revogavel continua barrando
# renovacao. Fail-open: erro de Redis nunca derruba a autenticacao.
_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
_DENYLIST_PREFIX = "revoked:"
_redis_client = None              # cache do cliente (lazy)
_denylist_aviso_emitido = False   # garante um unico log de aviso


def _get_denylist_redis():
    """Cliente Redis (sync) para a denylist, ou None se indisponivel.

    Lazy + cacheado. Sem REDIS_URL retorna None (degrada). Se o pacote `redis`
    nao estiver instalado ou a URL for invalida, avisa uma vez e retorna None.
    """
    global _redis_client, _denylist_aviso_emitido
    if not _REDIS_URL:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis as _redis  # import local: dependencia opcional (prod)

        _redis_client = _redis.Redis.from_url(
            _REDIS_URL, socket_timeout=1, socket_connect_timeout=1
        )
        return _redis_client
    except Exception:  # pragma: no cover - pacote ausente / URL invalida
        if not _denylist_aviso_emitido:
            log.warning(
                "REDIS_URL definido mas o cliente Redis nao pode ser criado — "
                "denylist de access token DESATIVADA (revogacao instantanea perdida)."
            )
            _denylist_aviso_emitido = True
        return None


def _aviso_denylist_indisponivel() -> None:
    global _denylist_aviso_emitido
    if not _denylist_aviso_emitido:
        log.warning(
            "Denylist de access token indisponivel (REDIS_URL ausente ou Redis "
            "inacessivel) — logout nao revoga o access instantaneamente; conta-se "
            "com o TTL curto do JWT + revogacao do refresh."
        )
        _denylist_aviso_emitido = True


def revogar_jti(jti: str, exp: int | None) -> bool:
    """Adiciona um `jti` a denylist com TTL = segundos ate `exp`.

    Idempotente. Retorna True se gravou no Redis, False se degradou (sem store
    ou ja expirado). Erro de Redis nao propaga (fail-open) — logout nunca quebra.
    """
    if not jti:
        return False
    cli = _get_denylist_redis()
    if cli is None:
        _aviso_denylist_indisponivel()
        return False
    # TTL = tempo restante ate exp; sem exp usa o TTL maximo do access (defesa).
    if exp is not None:
        ttl = int(exp - datetime.now(timezone.utc).timestamp())
    else:
        ttl = _JWT_TTL_MIN * 60
    if ttl <= 0:
        return False  # ja expirou: a propria validacao de exp ja barra
    try:
        cli.setex(f"{_DENYLIST_PREFIX}{jti}", ttl, "1")
        return True
    except Exception:  # pragma: no cover - Redis caiu: fail-open
        _aviso_denylist_indisponivel()
        return False


def jti_revogado(jti: str) -> bool:
    """True se o `jti` esta na denylist. Fail-open: erro de Redis -> False."""
    if not jti:
        return False
    cli = _get_denylist_redis()
    if cli is None:
        return False
    try:
        return cli.exists(f"{_DENYLIST_PREFIX}{jti}") > 0
    except Exception:  # pragma: no cover - Redis caiu: fail-open (nao barra tudo)
        return False


def gerar_refresh_token() -> str:
    """Token opaco URL-safe (~64 chars). NUNCA é um JWT."""
    return _secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """sha256 hex (64 chars). Deterministico — usado para lookup no banco."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_senha(senha: str) -> str:
    """Hash bcrypt da senha (uso: criar usuario, atualizar senha)."""
    return bcrypt.hashpw(_senha_72(senha), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Constant-time comparison via bcrypt.

    Senhas com mais de 72 bytes sao truncadas a 72 bytes (comportamento
    historico do passlib com truncate_error=False; bcrypt usa no maximo 72).
    Retorna False (em vez de levantar excecao) para entradas invalidas —
    inclusive senha/hash que nao sejam str (None, bytes), preservando a
    paridade com o `except Exception` do passlib e evitando 500 no login.
    """
    if not isinstance(senha, str) or not isinstance(hash_armazenado, str):
        return False
    try:
        return bcrypt.checkpw(_senha_72(senha), hash_armazenado.encode("utf-8"))
    except (ValueError, TypeError):  # hash invalido / formato nao bcrypt
        return False


# ── JWT ─────────────────────────────────────────────────────────────────────


class TokenPayload(BaseModel):
    """Claims tipados do JWT."""

    sub: str  # subject (cliente_id ou identificador)
    email: Optional[str] = None
    cliente_id: Optional[str] = None
    org_id: Optional[str] = None  # tenant (firma) — RLS por organização
    superadmin: bool = False  # acesso cross-org (leitura) — só o admin por env
    role: str = "user"
    jti: Optional[str] = None  # JWT ID — chave da denylist de revogação (#9)
    exp: Optional[int] = None
    iat: Optional[int] = None


def emitir_token(
    sub: str,
    email: Optional[str] = None,
    cliente_id: Optional[str] = None,
    org_id: Optional[str] = None,
    role: str = "user",
    superadmin: bool = False,
    ttl_min: Optional[int] = None,
) -> str:
    """Cria um JWT assinado. Default expira em ORGCONC_JWT_TTL_MIN minutos."""
    agora = datetime.now(timezone.utc)
    iat = int(agora.timestamp())
    payload = {
        "sub": sub,
        "iat": iat,
        "nbf": iat,  # not-before: token invalido antes de iat
        "jti": _uuid.uuid4().hex,  # JWT ID unico (32 chars) p/ revogacao/auditoria
        "exp": int((agora + timedelta(minutes=ttl_min or _JWT_TTL_MIN)).timestamp()),
        "role": role,
    }
    if email:
        payload["email"] = email
    if cliente_id:
        payload["cliente_id"] = cliente_id
    if org_id:
        payload["org_id"] = org_id
    if superadmin:
        payload["superadmin"] = True
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALG)


def decodificar_token(token: str) -> TokenPayload:
    """Decodifica e valida assinatura + exp + denylist. Levanta HTTPException 401.

    Alem da assinatura/exp, consulta a denylist por `jti` (#9): um token cujo
    `jti` foi revogado (logout/troca de senha) e rejeitado mesmo antes do exp.
    Sem Redis a denylist degrada (jti_revogado -> False): cai no comportamento
    anterior (revogacao so via refresh + TTL curto).
    """
    try:
        claims = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALG])
        payload = TokenPayload(**claims)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Token invalido: {type(e).__name__}")
    if payload.jti and jti_revogado(payload.jti):
        raise HTTPException(status_code=401, detail="Token revogado")
    return payload


# ── Dependency FastAPI ──────────────────────────────────────────────────────

# Token de servico compartilhado (scripts/CI). Quando configurado, desabilita o
# acesso anonimo: a API passa a exigir autenticacao mesmo fora de producao.
_LEGACY_SERVICE_TOKEN = os.environ.get("ORGCONC_AUTH_TOKEN", "").strip()


def auth_optional(
    request: Request = None,
    authorization: Optional[str] = Header(None),
) -> Optional[TokenPayload]:
    """Extrai e valida token (JWT ou service token). Retorna None se ausente."""
    token: Optional[str] = None

    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token:
        return None

    # Token de servico compartilhado (scripts/CI). Rejeitado em producao: la o
    # acesso deve ser sempre via JWT individual (auditavel, com exp/jti).
    if _LEGACY_SERVICE_TOKEN and token == _LEGACY_SERVICE_TOKEN:
        if _IS_PROD:
            raise HTTPException(
                status_code=401,
                detail="Token de servico legado desabilitado em producao — use JWT",
            )
        return TokenPayload(sub="service", role="service")

    return decodificar_token(token)


def current_user(
    request: Request = None,
    authorization: Optional[str] = Header(None),
) -> TokenPayload:
    """Dependency que exige autenticacao em producao (ou quando ha service token)."""
    payload = auth_optional(request, authorization)
    if payload is None:
        if _IS_PROD or _LEGACY_SERVICE_TOKEN:
            raise HTTPException(status_code=401, detail="Autenticacao obrigatoria")
        # Dev/staging sem service token: usuario anonimo
        return TokenPayload(sub="anonimo", role="anonymous")
    return payload


def autorizar_cliente(
    user: TokenPayload,
    cliente_id: str,
) -> None:
    """Verifica se o usuario tem acesso ao cliente solicitado.

    Roles privilegiados (admin, auditor, service) acessam qualquer cliente.
    User so acessa o proprio cliente_id; token sem cliente_id (legado) passa.

    'anonymous' NAO e privilegiado: so existe em dev/staging sem auth
    (current_user nunca o emite em producao). Em producao, por defesa em
    profundidade, anonymous e explicitamente negado para recursos com dono.
    """
    if user.role in ("admin", "auditor", "service"):
        return
    if user.role == "anonymous":
        if _IS_PROD:
            raise HTTPException(status_code=403, detail="Acesso negado a este cliente")
        return  # dev/staging: conveniencia de acesso sem token
    if not user.cliente_id:
        return  # token legado sem cliente_id (compat)
    if user.cliente_id == cliente_id:
        return
    raise HTTPException(status_code=403, detail="Acesso negado a este cliente")


def escopo_cliente_listagem(
    user: TokenPayload,
    cliente_id: Optional[str] = None,
) -> Optional[str]:
    """Resolve o `cliente_id` efetivo para uma listagem, sem vazamento cross-org (#23).

    Antes, um usuario multi-org podia passar um `cliente_id` arbitrario como
    filtro de listagem e ler dados de clientes de OUTRA org. Aqui restringimos:

    - Roles privilegiados (admin, auditor, service): podem escopar a qualquer
      `cliente_id` (ou None = todos), pois o isolamento por org ja e aplicado
      por outras camadas (RLS / org_id do token). Retorna o `cliente_id` pedido.
    - User comum COM cliente_id no token: so pode escopar ao PROPRIO cliente_id.
      Pedir outro cliente_id -> 403. Sem filtro (None) -> assume o proprio.
    - User comum SEM cliente_id no token (multi-org/legado): NAO pode passar um
      cliente_id arbitrario (era o furo). Pedir um cliente_id -> 403. Sem filtro
      -> retorna None (a listagem deve restringir por org_id do token a montante).
    - anonymous em producao -> 403 (sem dono nao ha escopo legitimo).

    Retorna o cliente_id efetivo (str) ou None (sem filtro por cliente).
    """
    if user.role in ("admin", "auditor", "service"):
        return cliente_id
    if user.role == "anonymous":
        if _IS_PROD:
            raise HTTPException(status_code=403, detail="Acesso negado")
        return cliente_id  # dev/staging: conveniencia
    if user.cliente_id:
        if cliente_id is None or cliente_id == user.cliente_id:
            return user.cliente_id
        raise HTTPException(status_code=403, detail="Acesso negado a este cliente")
    # User sem cliente_id no token: nao pode escolher um cliente arbitrario.
    if cliente_id is not None:
        raise HTTPException(status_code=403, detail="Acesso negado a este cliente")
    return None


def require_role(*roles: str):
    """Dependency factory: exige que o usuario autenticado tenha um dos `roles`.

    A autenticacao (401) ja e garantida por current_user; aqui aplicamos a
    autorizacao por papel (403). Uso:
        dependencies=[Depends(require_role("admin", "auditor", "service"))]
    ou como parametro: user = Depends(require_role("admin"))
    """
    permitidos = set(roles)

    def _dep(user: "TokenPayload" = Depends(current_user)) -> "TokenPayload":
        if user.role not in permitidos:
            raise HTTPException(status_code=403, detail="Acesso restrito")
        return user

    return _dep
