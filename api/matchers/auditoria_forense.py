"""Auditoria forense — orquestra o motor existente (regime_fiscal + forensics)
sobre as transações OFX, produzindo o resumo que SUBSTITUI o 'risco tributário'
enganoso do cruzamento simples.

Determinístico e sem rede. O enriquecimento cadastral (situação/porte, para
pós-baixa e MEI-teto) é OPCIONAL via `cadastro` (mapa cnpj→info pré-carregado);
sem ele, regime + padrões (smurfing, carrossel, valor redondo) e retenções já
funcionam. O enriquecimento pesado (BrasilAPI/RFB) deve ser job de background.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from api.matchers import forensics
from api.matchers.regime_fiscal import TETO_SIMPLES_EPP, AnaliseRegime, analisar_regime

_CLASSES = ("CRITICO", "ALTO", "MEDIO", "BAIXO")


@dataclass
class DisposicaoForense:
    data: str
    valor: float
    cnpj: str
    meio: str
    categoria_tributaria: str
    valor_retencao: float
    risk_score: int
    risco_classe: str
    sinais: list[str] = field(default_factory=list)


@dataclass
class ResumoAuditoria:
    regime: AnaliseRegime
    n_transacoes: int
    meses_observados: float
    heatmap: dict           # classe -> {"qtd", "volume"}
    retencao_estimada: float
    pos_baixa_qtd: int
    smurfing_qtd: int
    carrossel_qtd: int
    top_disposicoes: list[DisposicaoForense]


def _data_str(t) -> str:
    d = getattr(t, "data", "") or ""
    return d if isinstance(d, str) else d.isoformat()


def _meses_observados(transacoes) -> float:
    datas = sorted(_data_str(t)[:10] for t in transacoes if _data_str(t))
    if not datas:
        return 1.0
    try:
        d0 = date.fromisoformat(datas[0])
        d1 = date.fromisoformat(datas[-1])
        return max((d1 - d0).days + 1, 1) / 30.4375
    except ValueError:
        return 1.0


def _agregados(transacoes) -> forensics.AgregadosContraparte:
    agg = forensics.AgregadosContraparte()
    for t in sorted(transacoes, key=_data_str):
        cnpj = forensics._extrair_cnpj_str(t)
        if not cnpj:
            continue
        ds = _data_str(t)
        mes = ds[:7]
        agg.acumulado_mes[(cnpj, mes)] = agg.acumulado_mes.get((cnpj, mes), 0.0) + abs(t.valor)
        agg.primeira_data.setdefault(cnpj, ds)
        if t.valor > 0:
            agg.teve_credito[cnpj] = True
        else:
            agg.teve_debito[cnpj] = True
        agg.valores_dia.setdefault((cnpj, ds), []).append(abs(t.valor))
    return agg


def analisar_auditoria(transacoes, cadastro: dict | None = None, teto: float = TETO_SIMPLES_EPP) -> ResumoAuditoria:
    """Resumo forense de uma lista de Transacao (OFX). `cadastro` = {cnpj: {situacao, data_situacao, porte}}."""
    cadastro = cadastro or {}
    creditos = sum(t.valor for t in transacoes if t.valor > 0)
    debitos = sum(t.valor for t in transacoes if t.valor < 0)
    meses = _meses_observados(transacoes)
    regime = analisar_regime(creditos, debitos, meses, teto)

    agg = _agregados(transacoes)
    heatmap = {c: {"qtd": 0, "volume": 0.0} for c in _CLASSES}
    disposicoes: list[DisposicaoForense] = []
    retencao = 0.0
    pos_baixa = smurf = carross = 0

    for t in transacoes:
        ds = _data_str(t)
        cnpj = forensics._extrair_cnpj_str(t)
        info = cadastro.get(cnpj, {}) if cnpj else {}
        situacao = (info.get("situacao") or "").upper()
        porte = info.get("porte") or ""

        meio = forensics.detectar_meio(t.memo, t.nome)
        redondo = forensics.detectar_valor_redondo(t.valor)
        smurfing = forensics.detectar_smurfing(cnpj, ds, agg)
        carrossel = forensics.detectar_carrossel(cnpj, agg)
        primeira = forensics.detectar_primeira_vez(cnpj, ds, agg)
        acumulado = agg.acumulado_mes.get((cnpj, ds[:7]), 0.0)

        disp = ""
        if "BAIXADA" in situacao and t.valor < 0:
            data_baixa = info.get("data_situacao") or ""
            if data_baixa and ds and ds > data_baixa:
                disp = "ALERTA_POS_BAIXA"
                pos_baixa += 1

        score, classe = forensics.calcular_risk_score(
            t.valor, disp, situacao, porte, meio, redondo, smurfing, carrossel, primeira, acumulado
        )
        heatmap[classe]["qtd"] += 1
        heatmap[classe]["volume"] += abs(t.valor)

        trib = forensics.classificar_tributario(t.memo, t.nome, t.valor, cnpj, porte)
        ret = float(trib.get("valor_retencao") or 0.0)
        retencao += ret

        if smurfing:
            smurf += 1
        if carrossel:
            carross += 1

        sinais = [s for s in (disp, "SMURFING" if smurfing else "",
                              "CARROSSEL" if carrossel else "", redondo, primeira) if s]
        disposicoes.append(DisposicaoForense(
            data=ds, valor=round(t.valor, 2), cnpj=cnpj, meio=meio,
            categoria_tributaria=trib.get("categoria", "OUTRO"), valor_retencao=ret,
            risk_score=score, risco_classe=classe, sinais=sinais,
        ))

    top = sorted(disposicoes, key=lambda d: -d.risk_score)[:50]
    return ResumoAuditoria(
        regime=regime,
        n_transacoes=len(transacoes),
        meses_observados=round(meses, 2),
        heatmap={c: {"qtd": v["qtd"], "volume": round(v["volume"], 2)} for c, v in heatmap.items()},
        retencao_estimada=round(retencao, 2),
        pos_baixa_qtd=pos_baixa,
        smurfing_qtd=smurf,
        carrossel_qtd=carross,
        top_disposicoes=top,
    )


def cnpjs_das_transacoes(transacoes) -> list[str]:
    """CNPJs (14 dígitos) únicos extraídos do nome/memo das transações, em ordem."""
    vistos: list[str] = []
    seen: set[str] = set()
    for t in transacoes:
        c = forensics._extrair_cnpj_str(t)
        if c and c not in seen:
            seen.add(c)
            vistos.append(c)
    return vistos


def construir_cadastro(transacoes, cache: dict | None = None) -> dict:
    """Mapa cnpj -> {situacao, data_situacao, porte} a partir do cache de CNPJ (SEM rede).

    Use inline no /fiscal para ligar pós-baixa/MEI sem latência. O cache é populado
    pelo job `enriquecer_cadastro` (background, via BrasilAPI/RFB).
    """
    if cache is None:
        from api.matchers import cnpj_enricher
        cache = cnpj_enricher._carregar_cache()
    cadastro: dict[str, dict] = {}
    for cnpj in cnpjs_das_transacoes(transacoes):
        info = cache.get(cnpj)
        if info:
            cadastro[cnpj] = {
                "situacao": info.get("situacao", ""),
                "data_situacao": info.get("data_situacao", ""),
                "porte": info.get("porte", ""),
            }
    return cadastro


async def enriquecer_cadastro(transacoes, db=None, limite: int | None = None) -> int:
    """Job de background: enriquece (BrasilAPI → RFB local) os CNPJs ainda não
    cacheados e popula o cache. A próxima análise pega pós-baixa/MEI via cache.

    `limite=None` usa CNPJ_ENRICH_LIMITE (env var, default 300).
    Quando `db=None` e DB está disponível, cria sessão própria para acesso
    ao fallback RFB local (schema cnpj.*).
    """
    from api.core import config as _cfg
    from api.matchers import cnpj_enricher

    _limite = limite if limite is not None else _cfg.CNPJ_ENRICH_LIMITE
    cache = cnpj_enricher._carregar_cache()
    faltantes = [c for c in cnpjs_das_transacoes(transacoes) if c not in cache][:_limite]
    if not faltantes:
        return 0

    # Cria sessão própria para o RFB local quando nenhuma foi fornecida.
    # O background task não herda a sessão do request (ela já foi fechada).
    _own_db = False
    if db is None and _cfg.DB_DISPONIVEL and _cfg.SessionLocal is not None:
        db = _cfg.SessionLocal()
        _own_db = True
    try:
        await cnpj_enricher.enriquecer_lote(faltantes, db=db)
    finally:
        if _own_db and db is not None:
            await db.close()
    return len(faltantes)


def resumo_para_dict(r: ResumoAuditoria) -> dict:
    """Serializa o resumo forense para a resposta JSON da API."""
    return {
        "regime": {
            "volume_bruto": r.regime.volume_bruto,
            "volume_anualizado": r.regime.volume_anualizado,
            "teto": r.regime.teto,
            "multiplo_do_teto": r.regime.multiplo_do_teto,
            "classe": r.regime.classe,
            "incompativel": r.regime.incompativel,
        },
        "n_transacoes": r.n_transacoes,
        "meses_observados": r.meses_observados,
        "heatmap": r.heatmap,
        "retencao_estimada": r.retencao_estimada,
        "sinais": {"pos_baixa": r.pos_baixa_qtd, "smurfing": r.smurfing_qtd, "carrossel": r.carrossel_qtd},
        "top_disposicoes": [
            {"data": d.data, "valor": d.valor, "cnpj": d.cnpj, "meio": d.meio,
             "categoria_tributaria": d.categoria_tributaria, "risk_score": d.risk_score,
             "risco_classe": d.risco_classe, "sinais": d.sinais}
            for d in r.top_disposicoes[:20]
        ],
    }
