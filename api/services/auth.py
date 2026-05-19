"""Autenticacao JWT para OrgConc.

Implementa:
- Hashing de senhas com bcrypt (via passlib)
- Geracao e validacao de JWT (HS256)
- Dependency FastAPI `current_user` que substitui o Bearer compartilhado
- Fallback compativel: se ORGCONC_AUTH_TOKEN ainda existir, aceita como
  token "service" sem expiracao (uso em CI/scripts internos)

Variaveis de ambiente:
- ORGCONC_JWT_SECRET     : chave de assinatura (>=32 chars). Se ausente, gera
                           uma random no startup (tokens nao sobrevivem restart)
- ORGCONC_JWT_TTL_MIN    : expiracao em minutos (default 120)
- ORGCONC_AUTH_TOKEN     : (legacy) token compartilhado, aceito como service token
"""
from __future__ import annotations

import logging
import os
import secrets as _secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel

log = logging.getLogger("orgconc.auth")

# ── Config ──────────────────────────────────────────────────────────────────

_JWT_SECRET = os.environ.get("ORGCONC_JWT_SECRET", "").strip()
if not _JWT_SECRET:
    _JWT_SECRET = _secrets.token_urlsafe(48)
    log.warning(
        "ORGCONC_JWT_SECRET nao configurado — gerei um aleatorio. "
        "Tokens nao sobreviverao restart. Configure no .env em producao."
    )
elif len(_JWT_SECRET) < 32:
    log.warning("ORGCONC_JWT_SECRET tem menos de 32 chars — fraco. Aumente.")

_JWT_TTL_MIN = int(os.environ.get("ORGCONC_JWT_TTL_MIN", "120"))
_JWT_ALG = "HS256"

# Token legacy de servico (mantem retrocompat)
_LEGACY_SERVICE_TOKEN = os.environ.get("ORGCONC_AUTH_TOKEN", "").strip()

# Hashing (passlib)
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    """Hash bcrypt da senha (uso: criar usuario, atualizar senha)."""
    return _pwd_ctx.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Constant-time comparison via bcrypt."""
    try:
        return _pwd_ctx.verify(senha, hash_armazenado)
    except Exception:
        return False


# ── JWT ─────────────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    """Claims tipados do JWT."""
    sub: str          # subject (cliente_id ou identificador)
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
    payload = {
        "sub": sub,
        "iat": int(agora.timestamp()),
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

def auth_optional(authorization: Optional[str] = Header(None)) -> Optional[TokenPayload]:
    """Auth opcional. Retorna None se nao houver header. Levanta 401 se invalido.

    Usado em endpoints publicos que podem se beneficiar de saber quem chamou
    (ex: /health expoe banco_dados=ok mesmo sem auth).
    """
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Use 'Bearer <token>'")
    token = authorization.split(" ", 1)[1].strip()

    # Aceita token legacy (compatibilidade ate migrar 100%)
    if _LEGACY_SERVICE_TOKEN and _secrets.compare_digest(token, _LEGACY_SERVICE_TOKEN):
        return TokenPayload(sub="legacy-service", role="service")

    return decodificar_token(token)


def current_user(
    payload: Optional[TokenPayload] = Depends(auth_optional),
) -> TokenPayload:
    """Auth obrigatoria. Retorna TokenPayload ou levanta 401.

    Se ORGCONC_AUTH_TOKEN estiver vazio E nenhum Authorization for enviado,
    libera como 'anonymous' (modo dev). Em producao SEMPRE configurar
    ORGCONC_AUTH_TOKEN ou usar /auth/login.
    """
    if payload is not None:
        return payload
    if _LEGACY_SERVICE_TOKEN:
        # Modo "auth obrigatoria": exige header
        raise HTTPException(status_code=401, detail="Token Bearer ausente")
    # Modo dev sem auth configurada: usuario anonimo
    return TokenPayload(sub="anonymous", role="anonymous")
