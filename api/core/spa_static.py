"""StaticFiles com fallback de SPA (React Router) para o mount /app.

Bug que isto corrige (confirmado em produção, 2026-06-11): deep-link ou F5 em
rota interna do app (ex.: GET /app/laudo) devolvia 404 do FastAPI — o
`StaticFiles(html=True)` só serve index.html para o diretório raiz, não para
caminhos inexistentes, e a navegação client-side do React Router não cobre o
primeiro GET do browser.

Política de fallback: 404 em caminho SEM extensão → serve o index.html (é uma
rota de página do SPA, ex.: /app/laudo, /app/clientes). Caminho COM extensão
(.js, .css, .png…) continua 404 real — asset quebrado deve falhar visível, não
virar um HTML mascarado (quebraria o debugging de build).
"""
from __future__ import annotations

import posixpath

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


class SPAStaticFiles(StaticFiles):
    """StaticFiles que devolve index.html para rotas de página do SPA."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as exc:
            ultimo = posixpath.basename(path)
            if exc.status_code == 404 and "." not in ultimo:
                return await super().get_response("index.html", scope)
            raise
