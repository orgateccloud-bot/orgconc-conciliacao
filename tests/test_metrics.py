"""Testes dos endpoints /metrics e /transacoes."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ORGCONC_DATA_DIR", str(Path(__file__).resolve().parent / "_data_test"))
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# ── 503 sem DB ─────────────────────────────────────────────────────────────

def test_dashboard_bundle_503_sem_db():
    with patch("api.routers.metrics.DB_DISPONIVEL", False):
        r = client.get("/metrics/dashboard-bundle")
    assert r.status_code == 503


def test_trend_503_sem_db():
    with patch("api.routers.metrics.DB_DISPONIVEL", False):
        r = client.get("/metrics/trend")
    assert r.status_code == 503


def test_distribuicao_503_sem_db():
    with patch("api.routers.metrics.DB_DISPONIVEL", False):
        r = client.get("/metrics/distribuicao")
    assert r.status_code == 503


def test_heatmap_503_sem_db():
    with patch("api.routers.metrics.DB_DISPONIVEL", False):
        r = client.get("/metrics/heatmap")
    assert r.status_code == 503


def test_transacoes_recentes_503_sem_db():
    with patch("api.routers.transacoes.DB_DISPONIVEL", False):
        r = client.get("/transacoes/recentes")
    assert r.status_code == 503


# ── Validacao de parametros ────────────────────────────────────────────────

def test_dashboard_bundle_periodo_invalido_zero():
    r = client.get("/metrics/dashboard-bundle?periodo=0")
    assert r.status_code == 422


def test_dashboard_bundle_periodo_invalido_muito_grande():
    r = client.get("/metrics/dashboard-bundle?periodo=999")
    assert r.status_code == 422


def test_heatmap_periodo_minimo():
    """heatmap exige periodo >= 7 dias."""
    r = client.get("/metrics/heatmap?periodo=3")
    assert r.status_code == 422


def test_transacoes_limit_invalido():
    r = client.get("/transacoes/recentes?limit=0")
    assert r.status_code == 422


def test_transacoes_limit_acima_do_max():
    r = client.get("/transacoes/recentes?limit=500")
    assert r.status_code == 422


# ── Cache ───────────────────────────────────────────────────────────────────

def test_invalidar_cache_metrics_clear_total():
    from api.routers.metrics import _bundle_cache, invalidar_cache_metrics
    _bundle_cache["user-x:30"] = (0.0, {"dummy": True})
    _bundle_cache["user-y:30"] = (0.0, {"dummy": True})
    invalidar_cache_metrics()
    assert _bundle_cache == {}


def test_invalidar_cache_metrics_por_user():
    from api.routers.metrics import _bundle_cache, invalidar_cache_metrics
    _bundle_cache.clear()
    _bundle_cache["user-x:30"] = (0.0, {"dummy": True})
    _bundle_cache["user-y:30"] = (0.0, {"dummy": True})
    invalidar_cache_metrics(user_sub="user-x")
    assert "user-x:30" not in _bundle_cache
    assert "user-y:30" in _bundle_cache


# ── Smoke: rota registrada e responde ──────────────────────────────────────

def test_metrics_rotas_registradas():
    """Sanity: rotas existem na app (mesmo que retornem 503/422)."""
    paths = {r.path for r in app.routes}
    assert "/metrics/dashboard-bundle" in paths
    assert "/metrics/trend" in paths
    assert "/metrics/distribuicao" in paths
    assert "/metrics/heatmap" in paths
    assert "/metrics/trust-score" in paths
    assert "/transacoes/recentes" in paths
    assert "/audit/timeline" in paths
    assert "/audit/eventos/{evento_id}" in paths


def test_trust_score_503_sem_db():
    with patch("api.routers.metrics.DB_DISPONIVEL", False):
        r = client.get("/metrics/trust-score")
    assert r.status_code == 503


def test_trust_score_periodo_invalido():
    r = client.get("/metrics/trust-score?periodo=3")
    assert r.status_code == 422


def test_audit_timeline_503_sem_db():
    with patch("api.routers.audit.DB_DISPONIVEL", False):
        r = client.get("/audit/timeline")
    assert r.status_code == 503


def test_audit_evento_503_sem_db():
    with patch("api.routers.audit.DB_DISPONIVEL", False):
        r = client.get("/audit/eventos/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 503


def test_audit_evento_id_invalido():
    with patch("api.routers.audit.DB_DISPONIVEL", True):
        r = client.get("/audit/eventos/not-a-uuid")
    assert r.status_code == 400


def test_audit_timeline_limit_invalido():
    r = client.get("/audit/timeline?limit=0")
    assert r.status_code == 422


# ── Trust score: cálculo determinístico ─────────────────────────────────

def test_descricao_score_faixas():
    from api.db.metrics import _descricao_score
    assert "Excelente" in _descricao_score(95)
    assert "Saudavel" in _descricao_score(80)
    assert "Atencao" in _descricao_score(60)
    assert "Critico" in _descricao_score(20)


# ── Audit: mascaramento PII no endpoint ─────────────────────────────────

def test_mascarar_payload_aplica_pii_mask_em_emails():
    from api.routers.audit import _mascarar_payload
    payload = {"email": "joao.silva@orgatec.cloud", "lista": ["test@x.com", 42], "nested": {"cpf": "123.456.789-00"}}
    out = _mascarar_payload(payload)
    assert "joao.silva@orgatec.cloud" not in str(out)
    assert "123.456.789-00" not in str(out)
    assert 42 in out["lista"]  # tipos não-string preservados


# ── PR 5 endpoints ─────────────────────────────────────────────────────────

def test_modelos_503_sem_db():
    with patch("api.routers.metrics.DB_DISPONIVEL", False):
        r = client.get("/metrics/modelos")
    assert r.status_code == 503


def test_activity_feed_503_sem_db():
    with patch("api.routers.activity.DB_DISPONIVEL", False):
        r = client.get("/activity/feed")
    assert r.status_code == 503


def test_activity_feed_limit_invalido():
    r = client.get("/activity/feed?limit=0")
    assert r.status_code == 422


def test_ai_insights_503_sem_db():
    with patch("api.routers.ai.DB_DISPONIVEL", False):
        r = client.get("/ai/insights/dashboard")
    assert r.status_code == 503


def test_ai_insights_periodo_invalido():
    r = client.get("/ai/insights/dashboard?periodo=3")
    assert r.status_code == 422


def test_pr5_rotas_registradas():
    paths = {r.path for r in app.routes}
    assert "/metrics/modelos" in paths
    assert "/activity/feed" in paths
    assert "/ai/insights/dashboard" in paths


# ── AI Insights: fallback heuristico (sem API key) ───────────────────────

def test_insights_heuristicos_total_zero():
    from api.services.ai_insights import _insights_heuristicos
    out = _insights_heuristicos({"conciliacoes": 0})
    assert len(out) == 1
    assert out[0]["tipo"] == "info"
    assert "Nenhuma" in out[0]["titulo"]


def test_insights_heuristicos_taxa_alta_warn():
    from api.services.ai_insights import _insights_heuristicos
    out = _insights_heuristicos({
        "conciliacoes": 10, "anomalias": 5, "taxa_anomalias_pct": 15.0, "delta": None,
    })
    assert any(i["tipo"] == "warn" for i in out)


def test_insights_heuristicos_operacao_limpa_success():
    from api.services.ai_insights import _insights_heuristicos
    out = _insights_heuristicos({
        "conciliacoes": 10, "anomalias": 0, "taxa_anomalias_pct": 0.0, "delta": None,
    })
    assert any(i["tipo"] == "success" for i in out)


def test_insights_validar_sanitiza_tipo_invalido():
    from api.services.ai_insights import _validar_insight
    out = _validar_insight({"tipo": "wrong", "titulo": "x" * 200, "texto": "y" * 300})
    assert out["tipo"] == "info"
    assert len(out["titulo"]) <= 80
    assert len(out["texto"]) <= 240


def test_insights_heuristicos_taxa_baixa_info():
    from api.services.ai_insights import _insights_heuristicos
    out = _insights_heuristicos({
        "conciliacoes": 10, "anomalias": 3, "taxa_anomalias_pct": 3.0, "delta": None,
    })
    # taxa entre 0 e 10 → tipo info
    assert any(i["tipo"] == "info" for i in out)


def test_insights_heuristicos_volume_crescente_adiciona_insight():
    from api.services.ai_insights import _insights_heuristicos
    out = _insights_heuristicos({
        "conciliacoes": 50, "anomalias": 0, "taxa_anomalias_pct": 0.0,
        "delta": {"transacoes_pct": 35.0},
    })
    titulos = [i["titulo"] for i in out]
    assert any("cresceu" in t for t in titulos)


def test_get_insights_cache_hit():
    """Sem refresh + cache válido → retorna direto do cache, não chama Claude."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from unittest.mock import AsyncMock, MagicMock
    from api.services.ai_insights import get_insights
    from api.db.models import AiInsightsCache

    cached_entry = MagicMock(spec=AiInsightsCache)
    cached_entry.payload = {"insights": [{"tipo": "info", "titulo": "cacheado"}]}
    cached_entry.gerado_em = datetime.now(timezone.utc) - timedelta(hours=2)
    cached_entry.expira_em = datetime.now(timezone.utc) + timedelta(hours=22)

    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = cached_entry
    db.execute = AsyncMock(return_value=result)

    out = asyncio.run(get_insights(db, actor_sub="u1", periodo_dias=30, refresh=False))
    assert out["from_cache"] is True
    assert out["insights"][0]["titulo"] == "cacheado"
    db.add.assert_not_called()  # não criou novo cache


def test_get_insights_refresh_ignora_cache():
    """refresh=True → ignora cache e gera novo (cai em fallback heurístico sem API key)."""
    import asyncio
    import os
    from unittest.mock import AsyncMock, MagicMock, patch
    from api.services.ai_insights import get_insights

    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    # Mock das chamadas de agregação (todas retornam vazio)
    with patch("api.services.ai_insights.crud_metrics") as m, \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
        m.agregar_kpis = AsyncMock(return_value={"conciliacoes": 0})
        m.distribuicao_modo = AsyncMock(return_value=[])
        m.serie_temporal = AsyncMock(return_value=[])
        out = asyncio.run(get_insights(db, actor_sub="u2", periodo_dias=30, refresh=True))
    assert out["from_cache"] is False
    assert out["insights"]  # ao menos 1 insight heurístico
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
