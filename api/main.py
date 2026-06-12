"""API de Conciliacao Bancaria — ORGATEC OrgConc.

Execucao:
    uvicorn api.main:app --reload --port 8765
"""
from __future__ import annotations

import hmac
import logging
import os

from fastapi import HTTPException, Request

from api.core.bootstrap import criar_app
from api.core.spa_static import SPAStaticFiles
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
    jobs as jobs_router,
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
app.include_router(jobs_router.router)

# === Versionamento de API: /v1 (dual-mount, P2 #10) ===
# As rotas de negócio respondem TAMBÉM sob /v1/* (alias estável p/ clientes de
# API), mantendo a raiz como retrocompat do frontend atual — nada quebra.
# auth_routes TAMBÉM responde sob /v1 — com UMA exceção de uso: o cookie
# httpOnly de refresh é emitido com path fixo "/auth" (escopo mínimo), então o
# browser só o envia para /auth/* — refresh e logout DEVEM ser chamados na
# raiz (/auth/refresh, /auth/logout). Login/me/orgs/usuarios funcionam em
# ambos (Set-Cookie no login define o path do cookie independentemente da URL
# chamada). Documentado também em orgconc-react/src/lib/api.ts.
# Fora do /v1, de propósito: /metrics e /app (infra Prometheus/SPA).
# include_in_schema=False: o OpenAPI documenta o caminho canônico (raiz) uma vez.
_V1_ROUTERS = (
    health.router,
    auth_routes.router,
    clientes.router,
    conciliacao.router,
    exports.router,
    conciliacoes_list.router,
    metrics_router.router,
    audit_router.router,
    ai_router.router,
    activity_router.router,
    transacoes_router.router,
    matchers_router.router,
    guias_router.router,
    contratos_router.router,
    fiscal_router.router,
    jobs_router.router,
)
for _v1_router in _V1_ROUTERS:
    app.include_router(_v1_router, prefix="/v1", include_in_schema=False)

# Frontend React (SPA) — servido em /app quando o build existe (orgconc-react/dist).
# Em produção o build é gerado no Dockerfile multi-stage e servido same-origin pela
# própria API (GitHub Pages foi removido); este mount cobre prod e o uso local/Docker
# após `npm run build` em orgconc-react/. SPAStaticFiles: deep-link/F5 em rota
# interna (ex.: /app/laudo) serve o index.html — sem ele dava 404 em produção.
if REACT_DIST.exists():
    app.mount("/app", SPAStaticFiles(directory=str(REACT_DIST), html=True), name="react_app")
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
def prometheus_metrics(request: Request):
    """Exposição de métricas no formato Prometheus (text/plain).

    Proteção: se ORGCONC_METRICS_TOKEN estiver definido, exige
    `Authorization: Bearer <token>` (scraper Prometheus configura via
    authorization.credentials). Em produção SEM token configurado o endpoint
    fica fechado (404 — não revela existência); em dev permanece aberto.
    """
    esperado = os.environ.get("ORGCONC_METRICS_TOKEN", "").strip()
    if esperado:
        auth = request.headers.get("authorization", "")
        if not hmac.compare_digest(auth, f"Bearer {esperado}"):
            raise HTTPException(status_code=404, detail="Not Found")
    elif _IS_PROD:
        raise HTTPException(status_code=404, detail="Not Found")
    return metrics_endpoint()
