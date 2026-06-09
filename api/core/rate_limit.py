from __future__ import annotations

import os as _os

import jwt as _jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _get_rate_key(request: Request) -> str:
    """Rate limit por sub JWT quando disponivel, senao por IP remoto."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        secret = _os.environ.get("ORGCONC_JWT_SECRET", "")
        if secret:
            try:
                claims = _jwt.decode(
                    auth[7:],
                    secret,
                    algorithms=["HS256"],
                    options={"verify_exp": False},
                )
                sub = claims.get("sub", "")
                if sub:
                    return f"sub:{sub}"
            except (_jwt.InvalidTokenError, AttributeError, KeyError):
                # Token malformado ou sub ausente — cai pro IP
                pass
    return get_remote_address(request)


# Storage do rate-limit: in-memory por padrao (ok p/ 1 replica). Se REDIS_URL
# estiver definido, usa Redis como store COMPARTILHADO entre replicas/workers —
# necessario ao escalar horizontalmente (senao cada processo conta o seu limite).
# Requer o pacote `redis` (em requirements-prod). Sem REDIS_URL, nada muda.
_redis_url = _os.environ.get("REDIS_URL", "").strip()
_limiter_kwargs: dict = {
    "key_func": _get_rate_key,
    "default_limits": ["120/minute"],
    # Adiciona X-RateLimit-Limit/Remaining/Reset + Retry-After nas respostas 429.
    "headers_enabled": True,
}
if _redis_url:
    _limiter_kwargs["storage_uri"] = _redis_url

limiter = Limiter(**_limiter_kwargs)
