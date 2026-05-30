from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.db import refresh_tokens as refresh_repo
from api.schemas import LoginPayload
from api.schemas_responses import (
    LoginResponse,
    LogoutResponse,
    MeResponse,
    RefreshResponse,
)
from api.services.auth import (
    REFRESH_TTL_DAYS,
    TokenPayload,
    current_user,
    emitir_token,
    gerar_refresh_token,
    hash_refresh_token,
    hash_senha,
    verificar_senha,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_DUMMY_HASH = hash_senha("__orgconc_dummy_timing_constant_2026__")

_COOKIE_NAME = "orgconc_token"
_REFRESH_COOKIE_NAME = "orgconc_refresh"
_COOKIE_TTL = int(os.environ.get("ORGCONC_JWT_TTL_MIN", "15")) * 60
_REFRESH_COOKIE_TTL = REFRESH_TTL_DAYS * 24 * 3600
_IS_HTTPS = os.environ.get("ORGCONC_ENV", "").strip().lower() in ("production", "prod") or \
            os.environ.get("ORGCONC_HTTPS_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_IS_HTTPS,
        samesite="strict",
        path="/",
        max_age=_COOKIE_TTL,
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_IS_HTTPS,
        samesite="strict",
        path="/auth",      # so vai para endpoints /auth/*
        max_age=_REFRESH_COOKIE_TTL,
    )


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _client_ua(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _emitir_refresh_persistido(
    sub: str,
    request: Request,
) -> str:
    """Cria e persiste um refresh token. Retorna o token plain (cliente)."""
    token_plain = gerar_refresh_token()
    expira = datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS)
    async with SessionLocal() as db:
        await refresh_repo.criar(
            db,
            sub=sub,
            token_hash=hash_refresh_token(token_plain),
            expira_em=expira,
            ip=_client_ip(request),
            user_agent=_client_ua(request),
        )
    return token_plain


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def auth_login(request: Request, response: Response, payload: LoginPayload):
    admin_email = os.environ.get("ORGCONC_ADMIN_EMAIL", "").strip().lower()
    admin_hash = os.environ.get("ORGCONC_ADMIN_SENHA_HASH", "").strip()
    if not admin_email or not admin_hash:
        raise HTTPException(
            status_code=503,
            detail="Auth nao configurada — defina ORGCONC_ADMIN_EMAIL e ORGCONC_ADMIN_SENHA_HASH no .env",
        )
    email_ok = payload.email.strip().lower() == admin_email
    hash_a_usar = admin_hash if email_ok else _DUMMY_HASH
    senha_ok = verificar_senha(payload.senha, hash_a_usar)
    if not (email_ok and senha_ok):
        raise HTTPException(status_code=401, detail="Credenciais invalidas")

    access_token = emitir_token(sub=admin_email, email=admin_email, role="admin")
    _set_auth_cookie(response, access_token)

    # Refresh token opcional: so emite se DB esta disponivel para persistir
    payload_resp: dict = {"access_token": access_token, "token_type": "bearer"}
    if DB_DISPONIVEL:
        refresh_plain = await _emitir_refresh_persistido(admin_email, request)
        _set_refresh_cookie(response, refresh_plain)
        payload_resp["refresh_emitted"] = True
        payload_resp["refresh_ttl_days"] = REFRESH_TTL_DAYS
    else:
        payload_resp["refresh_emitted"] = False
        payload_resp["refresh_motivo"] = "db_indisponivel"

    return payload_resp


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("30/minute")
async def auth_refresh(request: Request, response: Response):
    """Rotaciona o refresh token e emite novo access token.

    Anti-replay: o refresh antigo eh revogado imediatamente. Se um cliente
    apresentar um refresh ja revogado, retornamos 401 (possivel comprometimento).
    """
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Refresh indisponivel — DB nao configurado")

    rt_plain = request.cookies.get(_REFRESH_COOKIE_NAME)
    if not rt_plain:
        raise HTTPException(401, "Refresh token ausente")

    rt_hash = hash_refresh_token(rt_plain)
    async with SessionLocal() as db:
        row = await refresh_repo.buscar_ativo_por_hash(db, rt_hash)
        if not row:
            # Pode ser: expirado, revogado, ou nunca existiu. Resposta uniforme.
            raise HTTPException(401, "Refresh invalido ou expirado")

        # Rotacao
        novo_plain = gerar_refresh_token()
        novo_row = await refresh_repo.criar(
            db,
            sub=row.sub,
            token_hash=hash_refresh_token(novo_plain),
            expira_em=datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS),
            ip=_client_ip(request),
            user_agent=_client_ua(request),
        )
        await refresh_repo.revogar(db, row.id, substituido_por=novo_row.id)

    novo_access = emitir_token(sub=row.sub, email=row.sub, role="admin")
    _set_auth_cookie(response, novo_access)
    _set_refresh_cookie(response, novo_plain)
    return {
        "access_token": novo_access,
        "token_type": "bearer",
        "refresh_emitted": True,
        "refresh_ttl_days": REFRESH_TTL_DAYS,
    }


@router.post("/logout", response_model=LogoutResponse)
async def auth_logout(request: Request, response: Response):
    """Revoga o refresh atual e limpa cookies. Idempotente."""
    rt_plain = request.cookies.get(_REFRESH_COOKIE_NAME)
    if rt_plain and DB_DISPONIVEL:
        async with SessionLocal() as db:
            await refresh_repo.revogar_por_hash(db, hash_refresh_token(rt_plain))
    response.delete_cookie(key=_COOKIE_NAME, path="/", samesite="strict")
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path="/auth", samesite="strict")
    return {"detail": "Sessao encerrada"}


@router.post("/logout-all", response_model=LogoutResponse)
async def auth_logout_all(request: Request, response: Response, user: TokenPayload = Depends(current_user)):
    """Logout global — revoga TODOS os refresh tokens do usuario."""
    revogados = 0
    if DB_DISPONIVEL:
        async with SessionLocal() as db:
            revogados = await refresh_repo.revogar_todos_do_sub(db, user.sub)
    response.delete_cookie(key=_COOKIE_NAME, path="/", samesite="strict")
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path="/auth", samesite="strict")
    return {"detail": "Sessoes encerradas", "revogados": revogados}


@router.get("/me", response_model=MeResponse)
async def auth_me(user: TokenPayload = Depends(current_user)):
    return {"sub": user.sub, "email": user.email, "role": user.role}


@router.post("/hash", include_in_schema=False)
async def auth_hash_helper(payload: dict, _user: TokenPayload = Depends(current_user)):
    if os.environ.get("ORGCONC_ENV", "development").strip().lower() in ("production", "prod"):
        raise HTTPException(status_code=404, detail="Indisponivel")
    if _user.role == "anonymous":
        raise HTTPException(status_code=401, detail="Token Bearer obrigatorio para /hash")
    senha = payload.get("senha", "")
    if not senha or len(senha) < 8:
        raise HTTPException(status_code=400, detail="Senha minima de 8 chars")
    return {"hash": hash_senha(senha)}
