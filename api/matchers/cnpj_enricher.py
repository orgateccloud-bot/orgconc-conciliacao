"""Enriquecedor de CNPJ — BrasilAPI (preferido) com fallback para base RFB local.

Estratégia em cascata:
  1. Cache local em JSON  -> instantâneo, sem rede
  2. BrasilAPI público (dados frescos, atualização contínua) -> ~2 req/s
  3. Schema cnpj.* no Postgres (carregado via OrgNeural ETL) -> SELECT local
     como fallback offline quando BrasilAPI falhar/cair

Por que BrasilAPI primeiro: a base pública da RFB é atualizada
mensalmente; a BrasilAPI proxia dados mais frescos. A base local entra
como contingência (rede caiu, rate limit) e para auditoria offline.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import httpx

CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "cnpj_cache.json"
BRASILAPI_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@dataclass
class CnpjInfo:
    cnpj: str                       # 14 dígitos
    razao_social: str = ""
    nome_fantasia: str = ""
    situacao: str = ""              # ATIVA / BAIXADA / SUSPENSA / INAPTA / NULA
    data_situacao: str = ""         # AAAA-MM-DD
    uf: str = ""
    municipio: str = ""
    cnae_principal: str = ""        # código
    cnae_descricao: str = ""
    porte: str = ""
    capital_social: float = 0.0
    fonte: str = ""                 # "cache" / "rfb_local" / "brasilapi" / "erro"
    flag: str = ""                  # alerta opcional


# ────────────────────────────────────────────────────────────────────────
# Cache local em JSON
# ────────────────────────────────────────────────────────────────────────


def _carregar_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _salvar_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# ────────────────────────────────────────────────────────────────────────
# Fonte 1: schema cnpj.* (base RFB carregada via OrgNeural ETL)
# ────────────────────────────────────────────────────────────────────────


_SITUACAO_MAP = {
    "01": "NULA", "02": "ATIVA", "03": "SUSPENSA",
    "04": "INAPTA", "08": "BAIXADA",
}

_PORTE_MAP = {
    "01": "MICRO EMPRESA",
    "03": "EMPRESA DE PEQUENO PORTE",
    "05": "DEMAIS",
}


async def _consulta_rfb_local(db, cnpj: str) -> Optional[CnpjInfo]:
    """Consulta o schema cnpj local (carregado via OrgNeural ETL)."""
    from sqlalchemy import text

    # Verifica se o schema existe
    try:
        r = await db.execute(text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name='cnpj')"
        ))
        if not r.scalar():
            return None
    except Exception:
        return None

    sql = text("""
        SELECT
          emp.razao_social,
          e.nome_fantasia,
          e.situacao_cadastral,
          e.data_situacao_cadastral,
          e.uf,
          mun.descricao AS municipio,
          e.cnae_principal,
          cn.descricao AS cnae_descricao,
          emp.porte_empresa,
          emp.capital_social
        FROM cnpj.estabelecimentos e
        JOIN cnpj.empresas emp ON emp.cnpj_basico = e.cnpj_basico
        LEFT JOIN cnpj.cnaes cn ON cn.codigo = e.cnae_principal
        LEFT JOIN cnpj.municipios mun ON mun.codigo = e.municipio
        WHERE e.cnpj = :cnpj
    """)
    r = await db.execute(sql, {"cnpj": cnpj})
    row = r.fetchone()
    if not row:
        return None

    situacao = _SITUACAO_MAP.get(row[2] or "", row[2] or "")
    porte = _PORTE_MAP.get(row[8] or "", "NAO INFORMADO")
    flag = (
        "ALERTA: contraparte BAIXADA — transacao com empresa nao ativa"
        if situacao == "BAIXADA"
        else "ALERTA: contraparte INAPTA" if situacao == "INAPTA"
        else ""
    )
    return CnpjInfo(
        cnpj=cnpj,
        razao_social=row[0] or "",
        nome_fantasia=row[1] or "",
        situacao=situacao,
        data_situacao=str(row[3]) if row[3] else "",
        uf=row[4] or "",
        municipio=row[5] or "",
        cnae_principal=row[6] or "",
        cnae_descricao=row[7] or "",
        porte=porte,
        capital_social=float(row[9]) if row[9] is not None else 0.0,
        fonte="rfb_local",
        flag=flag,
    )


# ────────────────────────────────────────────────────────────────────────
# Fonte 2: BrasilAPI (fallback online)
# ────────────────────────────────────────────────────────────────────────


async def _consulta_brasilapi(client: httpx.AsyncClient, cnpj: str) -> Optional[CnpjInfo]:
    try:
        r = await client.get(BRASILAPI_URL.format(cnpj=cnpj))
    except (httpx.HTTPError, httpx.TimeoutException):
        return None
    if r.status_code == 404:
        return CnpjInfo(cnpj=cnpj, fonte="brasilapi", flag="CNPJ nao encontrado")
    if r.status_code != 200:
        return None
    data = r.json()

    sit_desc = (data.get("descricao_situacao_cadastral") or "").upper()
    porte = (data.get("porte") or "").upper()
    flag = ""
    if "BAIXADA" in sit_desc:
        flag = "ALERTA: contraparte BAIXADA"
    elif "INAPTA" in sit_desc:
        flag = "ALERTA: contraparte INAPTA"
    elif "SUSPENSA" in sit_desc:
        flag = "ALERTA: contraparte SUSPENSA"

    return CnpjInfo(
        cnpj=cnpj,
        razao_social=data.get("razao_social") or "",
        nome_fantasia=data.get("nome_fantasia") or "",
        situacao=sit_desc,
        data_situacao=data.get("data_situacao_cadastral") or "",
        uf=data.get("uf") or "",
        municipio=data.get("municipio") or "",
        cnae_principal=str(data.get("cnae_fiscal") or ""),
        cnae_descricao=data.get("cnae_fiscal_descricao") or "",
        porte=porte,
        capital_social=float(data.get("capital_social") or 0),
        fonte="brasilapi",
        flag=flag,
    )


# ────────────────────────────────────────────────────────────────────────
# Função pública: consulta com cascata + cache
# ────────────────────────────────────────────────────────────────────────


def normaliza_cnpj(s: str) -> str:
    return re.sub(r"\D", "", s or "")


# ────────────────────────────────────────────────────────────────────────
# Busca por NOME (quando o extrato não traz CNPJ — ex: compra cartão)
# ────────────────────────────────────────────────────────────────────────


def _normaliza_nome(s: str) -> str:
    """Remove prefixos e ruído do nome bancário para melhor match."""
    if not s:
        return ""
    texto = s.upper().strip()
    # Remove prefixos comuns
    for prefixo in ("FAV.:", "FAV:", "FAV.", "FAVORECIDO:", "PAGAMENTO PIX",
                    "REM.:", "REM:", "REMETENTE:", "PIX EMITIDO"):
        if texto.startswith(prefixo):
            texto = texto[len(prefixo):].strip(" :")
    # Remove sufixos de localização tipicos de cartão (UF/BR no final)
    texto = re.sub(r"\s+(BR|BRA|BRASIL)\s*$", "", texto)
    # Remove sequências de números longos (CNPJ mascarado, sufixos *.*)
    texto = re.sub(r"\b\d{6,}\b", "", texto)
    texto = re.sub(r"\*+\.?\d*-?\*+", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def buscar_cnpj_por_nome_no_cache(nome: str, cache: dict, min_score: int = 85) -> Optional[CnpjInfo]:
    """Fuzzy match do nome contra as razões sociais já no cache.

    Útil quando a transação não traz CNPJ (compra cartão) mas o mesmo
    estabelecimento aparece em outras transações com PIX/CNPJ identificado.

    Args:
        nome: nome bancário (ex: "CONCESSIONARIA EC ANAPOLIS BR")
        cache: cache de CnpjInfo já populados
        min_score: score mínimo do RapidFuzz (0-100) para aceitar match
    """
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        return None

    alvo = _normaliza_nome(nome)
    if len(alvo) < 6:
        return None

    candidatos = {
        cnpj: _normaliza_nome(info.get("razao_social") or "") + " " +
              _normaliza_nome(info.get("nome_fantasia") or "")
        for cnpj, info in cache.items()
        if info.get("razao_social") or info.get("nome_fantasia")
    }
    if not candidatos:
        return None

    # WRatio combina partial_ratio + token_sort + outros — bom para nomes parciais
    best = process.extractOne(alvo, candidatos, scorer=fuzz.WRatio, score_cutoff=min_score)
    if not best:
        return None
    nome_match, score, cnpj_match = best
    info = CnpjInfo(**cache[cnpj_match])
    info.fonte = "cache_fuzzy"
    info.flag = (info.flag + f" | fuzzy {score:.0f}%").strip(" |") if info.flag else f"fuzzy {score:.0f}%"
    return info


async def buscar_cnpj_por_nome_rfb(db, nome: str, limite: int = 5) -> Optional[CnpjInfo]:
    """Busca CNPJ na base RFB local por razão social ou nome fantasia.

    Requer schema cnpj.* carregado (via scripts/etl_cnpj_supabase.py).
    Quando há múltiplos candidatos, retorna None (ambíguo).
    """
    if db is None:
        return None

    from sqlalchemy import text

    try:
        r = await db.execute(text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name='cnpj')"
        ))
        if not r.scalar():
            return None
    except Exception:
        return None

    alvo = _normaliza_nome(nome)
    if len(alvo) < 6:
        return None

    # ILIKE com % nos dois lados — usa índice de trigram se existir, senão seq scan
    sql = text("""
        SELECT
          e.cnpj, emp.razao_social, e.nome_fantasia,
          e.situacao_cadastral, e.data_situacao_cadastral,
          e.uf, mun.descricao AS municipio, e.cnae_principal,
          cn.descricao AS cnae_descricao, emp.porte_empresa, emp.capital_social
        FROM cnpj.estabelecimentos e
        JOIN cnpj.empresas emp ON emp.cnpj_basico = e.cnpj_basico
        LEFT JOIN cnpj.cnaes cn ON cn.codigo = e.cnae_principal
        LEFT JOIN cnpj.municipios mun ON mun.codigo = e.municipio
        WHERE (emp.razao_social ILIKE :padrao
            OR e.nome_fantasia ILIKE :padrao)
          AND e.situacao_cadastral = '02'  -- só ATIVOS para evitar baixadas antigas
        LIMIT :lim
    """)
    rows = (await db.execute(sql, {"padrao": f"%{alvo}%", "lim": limite})).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        # Ambíguo — pegar o melhor por similaridade local
        try:
            from rapidfuzz import fuzz
            rows_scored = sorted(
                rows,
                key=lambda r: -fuzz.WRatio(alvo, (r[1] or "") + " " + (r[2] or ""))
            )
            best, second = rows_scored[0], rows_scored[1] if len(rows_scored) > 1 else None
            s1 = fuzz.WRatio(alvo, (best[1] or "") + " " + (best[2] or ""))
            s2 = fuzz.WRatio(alvo, (second[1] or "") + " " + (second[2] or "")) if second else 0
            if s1 - s2 < 5:  # empate técnico
                return None
            row = best
        except ImportError:
            return None
    else:
        row = rows[0]

    sit = _SITUACAO_MAP.get(row[3] or "", row[3] or "")
    porte = _PORTE_MAP.get(row[9] or "", "NAO INFORMADO")
    return CnpjInfo(
        cnpj=row[0],
        razao_social=row[1] or "",
        nome_fantasia=row[2] or "",
        situacao=sit,
        data_situacao=str(row[4]) if row[4] else "",
        uf=row[5] or "",
        municipio=row[6] or "",
        cnae_principal=row[7] or "",
        cnae_descricao=row[8] or "",
        porte=porte,
        capital_social=float(row[10]) if row[10] is not None else 0.0,
        fonte="rfb_nome",
        flag="match por nome (RFB)",
    )


async def enriquecer_um(
    cnpj: str,
    cache: dict,
    client: Optional[httpx.AsyncClient] = None,
    db=None,
    semaforo: Optional[asyncio.Semaphore] = None,
) -> CnpjInfo:
    """Enriquece UM CNPJ usando cascata: cache → RFB local → BrasilAPI."""
    cnpj = normaliza_cnpj(cnpj)
    if len(cnpj) != 14:
        return CnpjInfo(cnpj=cnpj, fonte="erro", flag="CNPJ invalido")

    # 1. Cache local — sempre primeiro (instantâneo, sem rede)
    if cnpj in cache:
        info = CnpjInfo(**cache[cnpj])
        info.fonte = "cache"
        return info

    # 2. BrasilAPI (preferida — dados mais frescos)
    if client is not None:
        for tentativa in range(3):
            if semaforo is not None:
                async with semaforo:
                    await asyncio.sleep(0.55)  # ~1.8 req/s — abaixo do limite BrasilAPI
                    info = await _consulta_brasilapi(client, cnpj)
            else:
                info = await _consulta_brasilapi(client, cnpj)
            if info:
                cache[cnpj] = asdict(info)
                return info
            # Backoff exponencial entre tentativas
            await asyncio.sleep(2 ** tentativa)

    # 3. Fallback: base RFB local (quando BrasilAPI falhou/sem rede)
    if db is not None:
        info = await _consulta_rfb_local(db, cnpj)
        if info:
            info.flag = (info.flag + " | via fallback RFB").strip(" |")
            cache[cnpj] = asdict(info)
            return info

    return CnpjInfo(cnpj=cnpj, fonte="erro", flag="BrasilAPI e RFB local falharam")


async def enriquecer_lote(
    cnpjs: list[str],
    db=None,
    max_concurrency: int = 3,
    progress_cb=None,
) -> dict[str, CnpjInfo]:
    """Enriquece uma lista de CNPJs em paralelo (com rate limit)."""
    cache = _carregar_cache()
    semaforo = asyncio.Semaphore(max_concurrency)
    resultados: dict[str, CnpjInfo] = {}

    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": "OrgConc/0.5"}) as client:
        async def _job(c: str):
            info = await enriquecer_um(c, cache, client, db, semaforo)
            resultados[normaliza_cnpj(c)] = info
            if progress_cb:
                progress_cb(len(resultados), len(cnpjs))

        await asyncio.gather(*[_job(c) for c in cnpjs])

    _salvar_cache(cache)
    return resultados
