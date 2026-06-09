"""API de Conciliacao Bancaria — ORGATEC OrgConc.

Execucao:
    uvicorn api.main:app --reload --port 8765
"""
from __future__ import annotations

import logging
import os

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles

from api.core.bootstrap import criar_app
from api.core.prometheus_metrics import metrics_endpoint
from api.core.config import (
    DB_DISPONIVEL,  # noqa: F401 — re-export p/ testes
    REACT_DIST,
    SessionLocal,  # noqa: F401 — re-export p/ testes
    crud_clientes,  # noqa: F401 — re-export p/ testes
    _LOG_JSON,
    _LOG_LEVEL,
    _MODELOS_VALIDOS,  # noqa: F401 — re-export p/ testes
)
from api.core.config import _IS_PROD_ENV as _IS_PROD  # noqa: F401 — re-export p/ testes
from api.core.observability import init_sentry
from api.routers import (
    activity as activity_router,
    ai as ai_router,
    audit as audit_router,
    auth_routes,
    clientes,
    conciliacao,
    conciliacoes_list,
    contratos as contratos_router,
    exports,
    fiscal as fiscal_router,
    guias as guias_router,
    health,
    matchers as matchers_router,
    metrics as metrics_router,
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
from api.services.auth import _LEGACY_SERVICE_TOKEN as AUTH_TOKEN  # noqa: F401 — re-export p/ testes
from api.services.conciliacao_llm import (  # noqa: F401 — re-export p/ testes
    chamar_modelo_async as _chamar_modelo_async,
    sintetizar_consenso as _sintetizar_consenso,
)
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
app.include_router(conciliacao.router)
app.include_router(exports.router)
app.include_router(conciliacoes_list.router)
app.include_router(metrics_router.router)
app.include_router(audit_router.router)
app.include_router(ai_router.router)
app.include_router(activity_router.router)
app.include_router(transacoes_router.router)
app.include_router(matchers_router.router)
app.include_router(guias_router.router)
app.include_router(contratos_router.router)
app.include_router(fiscal_router.router)

# Frontend React (SPA) — servido em /app quando o build existe (orgconc-react/dist).
# Em produção o build é gerado no Dockerfile multi-stage e servido same-origin pela
# própria API (GitHub Pages foi removido); este mount cobre prod e o uso local/Docker
# após `npm run build` em orgconc-react/.
if REACT_DIST.exists():
    app.mount("/app", StaticFiles(directory=str(REACT_DIST), html=True), name="react_app")
else:
    _frontend_log = logging.getLogger("orgconc.frontend")

    @app.get("/app", include_in_schema=False)
    @app.get("/app/{_caminho:path}", include_in_schema=False)
    def app_build_ausente(_caminho: str = ""):
        """Build do React ausente: falha explícita em vez de servir UI fantasma."""
        _frontend_log.warning(
            "Build do React ausente em %s — rode `npm run build` em orgconc-react/.",
            REACT_DIST,
        )
        raise HTTPException(
            status_code=503,
            detail="Frontend não compilado. Rode `npm run build` em orgconc-react/.",
        )


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """Exposição de métricas no formato Prometheus (text/plain)."""
    return metrics_endpoint()
