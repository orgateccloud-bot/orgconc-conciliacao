"""Rate-limit do OrgConc.

Estrategia de chave: por `sub` JWT quando disponivel, senao por IP remoto.
Storage: Redis se `REDIS_URL` estiver setado (obrigatorio em multi-worker prod),
         fallback `memory://` em dev local.
"""
from __future__ import annotations

import logging
import os as _os

import jwt as _jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

log = logging.getLogger("orgconc.ratelimit")


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
            except Exception:
                pass
    return get_remote_address(request)


_REDIS_URL = _os.environ.get("REDIS_URL", "").strip()
_IS_PROD = _os.environ.get("ORGCONC_ENV", "").strip().lower() in ("production", "prod")
_WORKERS = int(_os.environ.get("WORKERS", "1") or "1")

if not _REDIS_URL:
    # Em prod com 2+ workers, in-memory permite que o cliente burle o limite
    # (cada worker tem seu proprio contador). Avisar e seguir.
    if _IS_PROD and _WORKERS > 1:
        log.warning(
            "REDIS_URL ausente em producao com WORKERS=%d — rate-limit "
            "in-memory NAO e compartilhado entre workers. Configure REDIS_URL.",
            _WORKERS,
        )
    _storage_uri = "memory://"
else:
    # slowapi/limits usa esquema `redis://` ou `redis+sentinel://` etc.
    _storage_uri = _REDIS_URL


limiter = Limiter(
    key_func=_get_rate_key,
    default_limits=["120/minute"],
    storage_uri=_storage_uri,
    strategy="fixed-window",
)

log.info("Rate-limit storage: %s", "redis" if _storage_uri.startswith("redis") else "memory")
