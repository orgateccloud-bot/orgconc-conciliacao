"""Autenticacao JWT para OrgConc.

Implementa:
- Hashing de senhas com bcrypt (via passlib)
- Geracao e validacao de JWT (HS256)
- Dependency FastAPI `current_user` com acesso anonimo em dev/staging

Variaveis de ambiente:
- ORGCONC_JWT_SECRET    : chave de assinatura (>=32 chars). Se ausente, gera
                          uma random no startup (tokens nao sobrevivem restart)
- ORGCONC_JWT_TTL_MIN   : expiracao em minutos (default 120)
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets as _secrets
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
import jwt
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel

log = logging.getLogger("orgconc.auth")

# ── Bcrypt via passlib ───────────────────────────────────────────────────────
# truncate_error=False: senhas >72 bytes sao truncadas silenciosamente em vez
# de levantar ValueError (comportamento do bcrypt < 4.x). Evita quebra de CI.
_pwd_ctx = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False,
)

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


def gerar_refresh_token() -> str:
    """Token opaco URL-safe (~64 chars). NUNCA é um JWT."""
    return _secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """sha256 hex (64 chars). Deterministico — usado para lookup no banco."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_senha(senha: str) -> str:
    """Hash bcrypt da senha (uso: criar usuario, atualizar senha)."""
    return _pwd_ctx.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Constant-time comparison via bcrypt (passlib CryptContext).

    Senhas com mais de 72 bytes sao truncadas silenciosamente
    (bcrypt__truncate_error=False). Retorna False para hashes com formato
    invalido em vez de levantar excecao.
    """
    try:
        return _pwd_ctx.verify(senha, hash_armazenado)
    except Exception:  # noqa: BLE001 — hash invalido ou formato nao bcrypt
        return False


# ── JWT ─────────────────────────────────────────────────────────────────────


class TokenPayload(BaseModel):
    """Claims tipados do JWT."""

    sub: str  # subject (cliente_id ou identificador)
    email: Optional[str] = None
    cliente_id: Optional[str] = None
    role: str = "user"
    exp: Optional[int] = None
    iat: Optional[int] = None


def emitir_token(
    sub: str,
    email: Optional[str] = None,
    cliente_id: Optional[str] = None,
    role: str = "user",
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
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALG)


def decodificar_token(token: str) -> TokenPayload:
    """Decodifica e valida assinatura + exp. Levanta HTTPException 401."""
    try:
        claims = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALG])
        return TokenPayload(**claims)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Token invalido: {type(e).__name__}")


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

    Roles privilegiados (admin, auditor, anonymous) acessam qualquer cliente.
    User so acessa o proprio cliente_id; token sem cliente_id (legado) passa.
    """
    if user.role in ("admin", "auditor", "anonymous"):
        return
    if not user.cliente_id:
        return
    if user.cliente_id == cliente_id:
        return
    raise HTTPException(status_code=403, detail="Acesso negado a este cliente")
