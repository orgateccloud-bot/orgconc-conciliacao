"""Geracao de insights da IA para o dashboard, com cache hibrido em Postgres.

Comportamento:
- get_insights(actor, periodo, refresh=False) busca cache valido (nao expirado) na
  tabela ai_insights_cache. Se existir, retorna direto (custo zero).
- Se refresh=True ou cache expirou, chama Claude com prompt agregado das ultimas
  metricas + anomalias e salva no cache (TTL 24h).

Insight tipado: {tipo: "success"|"warn"|"info", titulo, texto, cta?}
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import metrics as crud_metrics
from api.db.models import AiInsightsCache
from api.services.conciliacao_llm import chamar_modelo_async

log = logging.getLogger("orgconc.ai_insights")

CACHE_TTL_HOURS = 24
MAX_INSIGHTS = 3


async def get_insights(
    db: AsyncSession,
    *,
    actor_sub: str,
    org_id: Optional[str] = None,
    periodo_dias: int = 30,
    refresh: bool = False,
) -> dict[str, Any]:
    """Retorna {insights, from_cache, gerado_em, expira_em}.

    A chave de cache inclui `org_id` (#30): firmas distintas nao compartilham
    insights mesmo que o actor_sub colida. `org_id` None = escopo do sistema.
    """
    if not refresh:
        cached = await _buscar_cache_valido(db, actor_sub, org_id, periodo_dias)
        if cached:
            return {
                "insights": cached.payload.get("insights", []),
                "from_cache": True,
                "gerado_em": cached.gerado_em.isoformat(),
                "expira_em": cached.expira_em.isoformat(),
            }

    insights = await _gerar(db, periodo_dias=periodo_dias)
    agora = datetime.now(timezone.utc)
    entry = AiInsightsCache(
        org_id=org_id,
        actor_sub=actor_sub,
        periodo_dias=periodo_dias,
        gerado_em=agora,
        expira_em=agora + timedelta(hours=CACHE_TTL_HOURS),
        payload={"insights": insights},
    )
    db.add(entry)
    await db.commit()
    return {
        "insights": insights,
        "from_cache": False,
        "gerado_em": entry.gerado_em.isoformat(),
        "expira_em": entry.expira_em.isoformat(),
    }


async def _buscar_cache_valido(
    db: AsyncSession, actor_sub: str, org_id: Optional[str], periodo_dias: int
) -> Optional[AiInsightsCache]:
    agora = datetime.now(timezone.utc)
    q = (
        select(AiInsightsCache)
        .where(
            AiInsightsCache.actor_sub == actor_sub,
            AiInsightsCache.periodo_dias == periodo_dias,
            AiInsightsCache.expira_em > agora,
        )
        .order_by(AiInsightsCache.gerado_em.desc())
        .limit(1)
    )
    if org_id is None:
        q = q.where(AiInsightsCache.org_id.is_(None))
    else:
        q = q.where(AiInsightsCache.org_id == org_id)
    return (await db.execute(q)).scalar_one_or_none()


async def _gerar(db: AsyncSession, *, periodo_dias: int) -> list[dict[str, Any]]:
    """Chama Claude com KPIs + distribuicao + trend agregados. Retorna lista de insights.

    Se ANTHROPIC_API_KEY ausente ou se Claude falhar, retorna insights heuristicos.
    """
    kpis = await crud_metrics.agregar_kpis(db, periodo_dias=periodo_dias)
    distribuicao = await crud_metrics.distribuicao_modo(db, periodo_dias=periodo_dias)
    trend = await crud_metrics.serie_temporal(db, periodo_dias=periodo_dias)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return _insights_heuristicos(kpis)

    contexto = {
        "periodo_dias": periodo_dias,
        "kpis": kpis,
        "distribuicao_modos": distribuicao,
        "trend_ultimos_pontos": trend[-7:] if trend else [],
    }
    prompt = (
        "Voce e um consultor de conciliacao bancaria analisando metricas operacionais "
        "de um escritorio contabil. Com base nas metricas em JSON abaixo, gere ATE "
        f"{MAX_INSIGHTS} insights curtos e acionaveis em portugues brasileiro. "
        "Cada insight deve ter: tipo (success|warn|info), titulo (max 60 chars), "
        "texto (1-2 frases, max 200 chars) e opcionalmente cta (call to action curto).\n\n"
        "Foque em padroes anomalos, tendencias e recomendacoes praticas. Evite jargao.\n\n"
        f"METRICAS:\n```json\n{json.dumps(contexto, ensure_ascii=False, indent=2)}\n```\n\n"
        "Responda APENAS com array JSON valido (sem cercas markdown). Formato exato:\n"
        '[{"tipo": "info", "titulo": "...", "texto": "...", "cta": "..."}]'
    )

    try:
        res = await chamar_modelo_async(
            api_key, prompt, "claude-haiku-4-5-20251001", "Haiku 4.5", 1500
        )
        if res.get("erro"):
            log.warning("Insights via Claude falhou: %s", res["erro"])
            return _insights_heuristicos(kpis)
        texto = (res.get("texto") or "").strip()
        if texto.startswith("```"):
            # Remove cercas markdown se Claude colocou apesar do pedido
            texto = texto.strip("`").lstrip("json").strip()
        insights = json.loads(texto)
        if not isinstance(insights, list):
            raise ValueError("Resposta nao e lista")
        # Sanitiza e limita
        return [_validar_insight(i) for i in insights[:MAX_INSIGHTS] if isinstance(i, dict)]
    except Exception as exc:
        log.warning("Falha ao parsear insights da IA: %s", exc)
        return _insights_heuristicos(kpis)


def _validar_insight(raw: dict) -> dict[str, Any]:
    tipo = raw.get("tipo", "info")
    if tipo not in ("success", "warn", "info"):
        tipo = "info"
    return {
        "tipo": tipo,
        "titulo": str(raw.get("titulo", "Insight"))[:80],
        "texto": str(raw.get("texto", ""))[:240],
        "cta": str(raw.get("cta", ""))[:40] or None,
    }


def _insights_heuristicos(kpis: dict[str, Any]) -> list[dict[str, Any]]:
    """Fallback quando Claude indisponivel — gera insights derivados das metricas."""
    out: list[dict[str, Any]] = []
    total = kpis.get("conciliacoes", 0)
    anom = kpis.get("anomalias", 0)
    taxa = kpis.get("taxa_anomalias_pct", 0)
    delta_tx = (kpis.get("delta") or {}).get("transacoes_pct")

    if total == 0:
        out.append({
            "tipo": "info",
            "titulo": "Nenhuma conciliacao no periodo",
            "texto": "Faca a primeira analise OFX para popular metricas e ativar insights da IA.",
            "cta": "Nova analise",
        })
        return out

    if taxa > 10:
        out.append({
            "tipo": "warn",
            "titulo": f"Taxa de anomalias elevada ({taxa}%)",
            "texto": f"{anom} anomalias detectadas em {total} conciliacoes. Revisar padroes recorrentes.",
            "cta": "Ver anomalias",
        })
    elif taxa > 0:
        out.append({
            "tipo": "info",
            "titulo": "Anomalias dentro do esperado",
            "texto": f"{anom} anomalias em {total} conciliacoes ({taxa}%). Padrao consistente.",
            "cta": None,
        })
    else:
        out.append({
            "tipo": "success",
            "titulo": "Operacao limpa",
            "texto": f"{total} conciliacoes sem anomalias no periodo. Manter rotina.",
            "cta": None,
        })

    if delta_tx is not None and delta_tx > 20:
        out.append({
            "tipo": "info",
            "titulo": f"Volume cresceu {round(delta_tx, 1)}%",
            "texto": "Aumento significativo vs. periodo anterior. Considere revisar capacidade operacional.",
            "cta": None,
        })

    return out
