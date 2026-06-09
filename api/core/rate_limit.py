from __future__ import annotations

import os as _os
import time as _time

import jwt as _jwt
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


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
# NÃO usamos headers_enabled=True: ele injeta headers em TODA resposta (sucesso
# inclusive), o que exigiria `response: Response` em cada um dos ~34 endpoints
# decorados (slowapi levanta se o handler não tiver esse parâmetro). Em vez disso,
# injetamos os headers só na resposta 429, via rate_limit_exceeded_handler abaixo.
_limiter_kwargs: dict = {
    "key_func": _get_rate_key,
    "default_limits": ["120/minute"],
}
if _redis_url:
    _limiter_kwargs["storage_uri"] = _redis_url

limiter = Limiter(**_limiter_kwargs)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handler do 429 com headers X-RateLimit-Limit/Remaining/Reset + Retry-After.

    Substitui o handler padrão do slowapi (que só injeta headers se headers_enabled,
    o qual quebraria o caminho de sucesso). Aqui os headers vão apenas no 429,
    derivados de `request.state.view_rate_limit` (limite + janela) que o slowapi
    popula antes de levantar a exceção. Defensivo: se algo faltar, mantém ao menos
    o Retry-After (exigência do roadmap P0 #3)."""
    response = JSONResponse(
        {"error": f"Rate limit exceeded: {exc.detail}"}, status_code=429
    )
    retry_after = 60
    cur = getattr(request.state, "view_rate_limit", None)
    if cur is not None:
        item, args = cur[0], cur[1]
        response.headers["X-RateLimit-Limit"] = str(item.amount)
        try:
            window = limiter.limiter.get_window_stats(item, *args)
            reset_epoch = 1 + window[0]
            response.headers["X-RateLimit-Remaining"] = str(window[1])
            response.headers["X-RateLimit-Reset"] = str(reset_epoch)
            retry_after = max(0, reset_epoch - int(_time.time()))
        except Exception:  # pragma: no cover - store indisponível: cai no default
            pass
    response.headers["Retry-After"] = str(retry_after)
    return response
