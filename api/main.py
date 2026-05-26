"""API de Conciliacao Bancaria — ORGATEC OrgConc.

Execucao:
    uvicorn api.main:app --reload --port 8765
"""
from __future__ import annotations

import os

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.core.bootstrap import criar_app
from api.core.config import (
    DB_DISPONIVEL,  # noqa: F401 — re-export p/ testes
    REACT_DIST,
    ROOT_DIR,
    STATIC_DIR,
    _LOG_JSON,
    _LOG_LEVEL,
    _MODELOS_VALIDOS,  # noqa: F401 — re-export p/ testes
)
from api.core.observability import init_sentry
from api.routers import (
    activity as activity_router,
    ai as ai_router,
    audit as audit_router,
    auth_routes,
    clientes,
    conciliacao,
    conciliacoes_list,
    exports,
    health,
    metrics as metrics_router,
    serpro,
    transacoes as transacoes_router,
)
from api.services.logging_estruturado import configurar_logging

# Re-export para testes e retrocompat
from api.parsers import (  # noqa: F401
    _chave_transacao,
    _classificar,
    _coletar_chaves_anomalas,
    _detectar_anomalias,
    _parse_arquivo,
    _parse_ofx,
    _parse_xml,
)
from api.services.excel import _gerar_xlsx  # noqa: F401
from api.services.db_persistence import salvar_no_banco as _salvar_no_banco  # noqa: F401
from api.services.render import render_html as _render_html  # noqa: F401
from api.services.storage import (  # noqa: F401
    carregar_dataset as _carregar_dataset,
    salvar_dataset as _salvar_dataset,
)

configurar_logging(nivel=_LOG_LEVEL, json_mode=_LOG_JSON)
init_sentry(release=os.environ.get("ORGCONC_RELEASE") or None)

app = criar_app()

app.include_router(health.router)
app.include_router(auth_routes.router)
app.include_router(clientes.router)
app.include_router(serpro.router)
app.include_router(conciliacao.router)
app.include_router(exports.router)
app.include_router(conciliacoes_list.router)
app.include_router(metrics_router.router)
app.include_router(audit_router.router)
app.include_router(ai_router.router)
app.include_router(activity_router.router)
app.include_router(transacoes_router.router)

# UI legada (periodo de transicao)
if STATIC_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui_legacy")

if REACT_DIST.exists():
    app.mount("/app", StaticFiles(directory=str(REACT_DIST), html=True), name="react_app")


@app.get("/deck", include_in_schema=False)
def frontend_legacy_redirect():
    """Dashboard HTML legado em frontend/."""
    html_path = ROOT_DIR / "frontend" / "index.html"
    if not html_path.exists():
        raise HTTPException(404, "Frontend nao encontrado")
    return FileResponse(str(html_path), media_type="text/html")
