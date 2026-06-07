"""Queries agregadas para o dashboard.

Consolida em queries SQL eficientes (uma por endpoint) para evitar N+1.
Todas funcoes async e recebem AsyncSession.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Conciliacao, LlmCostDaily, Transacao


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def agregar_kpis(db: AsyncSession, periodo_dias: int = 30) -> dict[str, Any]:
    """KPIs principais: conciliacoes, transacoes, anomalias, arquivos no periodo.

    Tambem retorna delta vs periodo anterior equivalente para mostrar tendencia.
    """
    desde = _now_utc() - timedelta(days=periodo_dias)
    desde_anterior = _now_utc() - timedelta(days=periodo_dias * 2)

    # Periodo atual
    q_atual = select(
        func.count(Conciliacao.id).label("conciliacoes"),
        func.coalesce(func.sum(Conciliacao.total_transacoes), 0).label("transacoes"),
        func.coalesce(func.sum(Conciliacao.total_anomalias), 0).label("anomalias"),
        func.coalesce(func.sum(Conciliacao.valor_total_credito + Conciliacao.valor_total_debito), 0).label("volume_total"),
    ).where(Conciliacao.criado_em >= desde)
    atual = (await db.execute(q_atual)).one()

    # Periodo anterior (para delta)
    q_anterior = select(
        func.count(Conciliacao.id).label("conciliacoes"),
        func.coalesce(func.sum(Conciliacao.total_transacoes), 0).label("transacoes"),
        func.coalesce(func.sum(Conciliacao.total_anomalias), 0).label("anomalias"),
    ).where(Conciliacao.criado_em >= desde_anterior, Conciliacao.criado_em < desde)
    anterior = (await db.execute(q_anterior)).one()

    def _delta_pct(novo: float, antigo: float) -> float | None:
        if antigo == 0:
            return None
        return round(((novo - antigo) / antigo) * 100, 1)

    transacoes = int(atual.transacoes or 0)
    anomalias = int(atual.anomalias or 0)
    taxa_anom = round(anomalias / transacoes * 100, 2) if transacoes else 0.0

    return {
        "periodo_dias": periodo_dias,
        "conciliacoes": int(atual.conciliacoes or 0),
        "transacoes": transacoes,
        "anomalias": anomalias,
        "volume_total": float(atual.volume_total or 0),
        "taxa_anomalias_pct": taxa_anom,
        "delta": {
            "conciliacoes_pct": _delta_pct(int(atual.conciliacoes or 0), int(anterior.conciliacoes or 0)),
            "transacoes_pct": _delta_pct(transacoes, int(anterior.transacoes or 0)),
            "anomalias_pct": _delta_pct(anomalias, int(anterior.anomalias or 0)),
        },
    }


async def serie_temporal(db: AsyncSession, periodo_dias: int = 30) -> list[dict[str, Any]]:
    """Serie diaria: data, conciliacoes, transacoes, anomalias."""
    desde = _now_utc() - timedelta(days=periodo_dias)
    dia = func.date_trunc("day", Conciliacao.criado_em).label("dia")
    q = (
        select(
            dia,
            func.count(Conciliacao.id).label("conciliacoes"),
            func.coalesce(func.sum(Conciliacao.total_transacoes), 0).label("transacoes"),
            func.coalesce(func.sum(Conciliacao.total_anomalias), 0).label("anomalias"),
        )
        .where(Conciliacao.criado_em >= desde)
        .group_by(dia)
        .order_by(dia)
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "data": r.dia.date().isoformat() if r.dia else None,
            "conciliacoes": int(r.conciliacoes or 0),
            "transacoes": int(r.transacoes or 0),
            "anomalias": int(r.anomalias or 0),
        }
        for r in rows
    ]


async def distribuicao_modo(db: AsyncSession, periodo_dias: int = 30) -> list[dict[str, Any]]:
    """Distribuicao por modo de conciliacao (simulacao/llm/multi/csv).

    Substitui a 'distribuicao por formato' (OFX/PDF/CSV/XML) — formato nao e
    persistido hoje; modo e o melhor proxy disponivel.
    """
    desde = _now_utc() - timedelta(days=periodo_dias)
    q = (
        select(
            Conciliacao.modo,
            func.count(Conciliacao.id).label("qtd"),
        )
        .where(Conciliacao.criado_em >= desde)
        .group_by(Conciliacao.modo)
        .order_by(func.count(Conciliacao.id).desc())
    )
    rows = (await db.execute(q)).all()
    return [{"modo": r.modo, "qtd": int(r.qtd or 0)} for r in rows]


async def heatmap_diario(db: AsyncSession, periodo_dias: int = 365) -> list[dict[str, Any]]:
    """Volume diario para heatmap estilo GitHub contribuitions.

    Retorna lista de {data, valor} onde valor = total_transacoes do dia.
    """
    desde = _now_utc() - timedelta(days=periodo_dias)
    dia = func.date_trunc("day", Conciliacao.criado_em).label("dia")
    q = (
        select(
            dia,
            func.coalesce(func.sum(Conciliacao.total_transacoes), 0).label("valor"),
        )
        .where(Conciliacao.criado_em >= desde)
        .group_by(dia)
        .order_by(dia)
    )
    rows = (await db.execute(q)).all()
    return [
        {"data": r.dia.date().isoformat() if r.dia else None, "valor": int(r.valor or 0)}
        for r in rows
    ]


async def listar_transacoes_recentes(
    db: AsyncSession,
    limit: int = 10,
    cliente_id=None,
) -> list[Transacao]:
    """Ultimas transacoes. Se cliente_id fornecido, filtra pelo tenant via JOIN."""
    q = select(Transacao).order_by(Transacao.criado_em.desc()).limit(limit)
    if cliente_id is not None:
        q = q.join(Conciliacao, Transacao.conciliacao_id == Conciliacao.id).where(
            Conciliacao.cliente_id == cliente_id
        )
    result = await db.execute(q)
    return list(result.scalars().all())


async def performance_modelos(db: AsyncSession, periodo_dias: int = 30) -> list[dict[str, Any]]:
    """Agrega uso e latencia media por modo de conciliacao.

    Como `modo` mapeia para LLM/Multi/Simulacao (nao especifica Haiku/Sonnet/Opus),
    o endpoint expoe AT NIVEL DE MODO. latency_ms_avg pode ser None enquanto a
    coluna nao for populada (PR 5 apenas adiciona a coluna).
    """
    desde = _now_utc() - timedelta(days=periodo_dias)
    q = (
        select(
            Conciliacao.modo,
            func.count(Conciliacao.id).label("qtd"),
            func.avg(Conciliacao.usage_latency_ms).label("latency_avg"),
            func.coalesce(func.sum(Conciliacao.total_transacoes), 0).label("tx"),
            func.coalesce(func.sum(Conciliacao.total_anomalias), 0).label("anom"),
        )
        .where(Conciliacao.criado_em >= desde)
        .group_by(Conciliacao.modo)
        .order_by(func.count(Conciliacao.id).desc())
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "modo": r.modo,
            "qtd": int(r.qtd or 0),
            "latency_ms_avg": int(r.latency_avg) if r.latency_avg is not None else None,
            "transacoes": int(r.tx or 0),
            "anomalias": int(r.anom or 0),
        }
        for r in rows
    ]


async def calcular_trust_score(db: AsyncSession, periodo_dias: int = 30) -> dict[str, Any]:
    """Score 0-100 derivado de metricas reais — sem inventar numeros.

    Componentes:
    - `taxa_sucesso`: % conciliacoes com 0 anomalias nos ultimos N dias (0-100)
    - `dias_sem_falha`: dias desde a ultima falha critica (cap em 30, normalizado 0-100)
    - `cobertura`: numero de conciliacoes / max esperado (sinaliza adopcao)

    Score final = media ponderada (0.5 * sucesso + 0.3 * dias_sem_falha + 0.2 * cobertura).
    """
    desde = _now_utc() - timedelta(days=periodo_dias)

    # Total e sem anomalias no periodo
    q_total = select(
        func.count(Conciliacao.id).label("total"),
        func.coalesce(
            func.sum(
                case((Conciliacao.total_anomalias == 0, 1), else_=0)
            ),
            0,
        ).label("limpas"),
        func.coalesce(func.sum(Conciliacao.total_anomalias), 0).label("anom"),
        func.coalesce(func.sum(Conciliacao.total_transacoes), 0).label("tx"),
    ).where(Conciliacao.criado_em >= desde)
    row = (await db.execute(q_total)).one()
    total = int(row.total or 0)
    limpas = int(row.limpas or 0)
    anom = int(row.anom or 0)
    tx = int(row.tx or 0)

    taxa_sucesso = (limpas / total * 100) if total else 100.0

    # Dias desde ultima conciliacao com anomalia
    q_ultima_falha = (
        select(Conciliacao.criado_em)
        .where(Conciliacao.total_anomalias > 0)
        .order_by(Conciliacao.criado_em.desc())
        .limit(1)
    )
    ultima = (await db.execute(q_ultima_falha)).scalar_one_or_none()
    if ultima is None:
        dias_sem_falha = periodo_dias
    else:
        delta = (_now_utc() - ultima).total_seconds() / 86400
        dias_sem_falha = min(delta, periodo_dias)
    score_dias = (dias_sem_falha / periodo_dias) * 100

    # Cobertura: heuristica simples — 1 conciliacao/dia esperado
    cobertura = min(total / max(periodo_dias, 1) * 100, 100)

    score = round(0.5 * taxa_sucesso + 0.3 * score_dias + 0.2 * cobertura)

    taxa_anomalias = round((anom / tx * 100), 2) if tx else 0.0

    return {
        "score": int(score),
        "periodo_dias": periodo_dias,
        "breakdown": {
            "taxa_sucesso_pct": round(taxa_sucesso, 1),
            "dias_sem_falha": round(dias_sem_falha, 1),
            "cobertura_pct": round(cobertura, 1),
        },
        "metricas": {
            "total_conciliacoes": total,
            "conciliacoes_limpas": limpas,
            "total_transacoes": tx,
            "total_anomalias": anom,
            "taxa_anomalias_pct": taxa_anomalias,
        },
        "descricao": _descricao_score(int(score)),
    }


def _descricao_score(score: int) -> str:
    if score >= 90:
        return "Excelente — operação estável e auditada"
    if score >= 75:
        return "Saudável — pequenos ajustes recomendados"
    if score >= 50:
        return "Atenção — revisar anomalias recentes"
    return "Crítico — auditoria manual recomendada"


async def custo_llm_resumo(db: AsyncSession, periodo_dias: int = 30) -> dict[str, Any]:
    """Resumo de custo Claude API + previsao de gastos a partir de llm_cost_daily.

    Calcula, a partir do historico diario persistido:
    - total no periodo de exibicao (custo USD + chamadas)
    - custo de hoje
    - burn rate diario = media dos ultimos 7 dias de CALENDARIO (dias sem registro
      contam como 0 — metrica conservadora que nao superestima em uso esporadico)
    - mes corrente: gasto ate agora, dias restantes, projecao linear ate o fim do mes
    - projecao para os proximos 30 dias (burn_rate * 30)
    - serie diaria para o grafico

    A janela buscada cobre simultaneamente o periodo de exibicao, o mes corrente e
    a janela de 7 dias do burn rate — mesmo quando ``periodo_dias`` e pequeno — para
    que as projecoes nunca fiquem sem dados.
    """
    hoje = _now_utc().date()
    inicio_mes = hoje.replace(day=1)
    desde_display = hoje - timedelta(days=periodo_dias - 1)
    desde_burn = hoje - timedelta(days=6)
    desde_query = min(desde_display, desde_burn, inicio_mes)

    q = (
        select(LlmCostDaily.dia, LlmCostDaily.custo_usd, LlmCostDaily.chamadas)
        .where(LlmCostDaily.dia >= desde_query)
        .order_by(LlmCostDaily.dia)
    )
    rows = (await db.execute(q)).all()

    por_dia_custo = {r.dia.isoformat(): float(r.custo_usd or 0) for r in rows}

    # Serie do grafico: apenas o periodo de exibicao solicitado.
    serie = [
        {
            "data": r.dia.isoformat(),
            "custo_usd": float(r.custo_usd or 0),
            "chamadas": int(r.chamadas or 0),
        }
        for r in rows
        if r.dia >= desde_display
    ]

    total_periodo_usd = round(sum(d["custo_usd"] for d in serie), 4)
    total_chamadas = sum(d["chamadas"] for d in serie)
    custo_hoje_usd = round(por_dia_custo.get(hoje.isoformat(), 0.0), 4)

    # Burn rate: media dos ultimos 7 dias de calendario (inclui dias zerados).
    custo_7d = sum(v for k, v in por_dia_custo.items() if k >= desde_burn.isoformat())
    burn_rate_diario_usd = round(custo_7d / 7, 4)

    # Mes corrente + projecao linear ate o ultimo dia do mes.
    custo_mes = round(
        sum(v for k, v in por_dia_custo.items() if k >= inicio_mes.isoformat()), 4
    )
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    dias_restantes = dias_no_mes - hoje.day
    projecao_fim_mes_usd = round(custo_mes + burn_rate_diario_usd * dias_restantes, 4)
    projecao_30d_usd = round(burn_rate_diario_usd * 30, 4)

    return {
        "periodo_dias": periodo_dias,
        "total_periodo_usd": total_periodo_usd,
        "total_chamadas": total_chamadas,
        "custo_hoje_usd": custo_hoje_usd,
        "burn_rate_diario_usd": burn_rate_diario_usd,
        "mes_corrente": {
            "custo_ate_agora_usd": custo_mes,
            "dias_no_mes": dias_no_mes,
            "dias_restantes": dias_restantes,
            "projecao_fim_mes_usd": projecao_fim_mes_usd,
        },
        "projecao_30d_usd": projecao_30d_usd,
        "serie_diaria": serie,
    }
