from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request

from api.core.rate_limit import limiter
from api.schemas import LoginPayload
from api.services.auth import current_user, emitir_token, hash_senha, verificar_senha, TokenPayload

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
@limiter.limit("10/minute")
async def auth_login(request: Request, payload: LoginPayload):
    admin_email = os.environ.get("ORGCONC_ADMIN_EMAIL", "").strip().lower()
    admin_hash = os.environ.get("ORGCONC_ADMIN_SENHA_HASH", "").strip()
    if not admin_email or not admin_hash:
        raise HTTPException(
            status_code=503,
            detail="Auth nao configurada — defina ORGCONC_ADMIN_EMAIL e ORGCONC_ADMIN_SENHA_HASH no .env",
        )
    if payload.email.strip().lower() != admin_email:
        raise HTTPException(status_code=401, detail="Credenciais invalidas")
    if not verificar_senha(payload.senha, admin_hash):
        raise HTTPException(status_code=401, detail="Credenciais invalidas")
    token = emitir_token(sub=admin_email, email=admin_email, role="admin")
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
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
