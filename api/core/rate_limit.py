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


limiter = Limiter(key_func=_get_rate_key, default_limits=["120/minute"])
