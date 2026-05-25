from __future__ import annotations

import asyncio
import logging
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from api.core.config import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_TOTAL_BYTES,
    MAX_UPLOAD_TOTAL_MB,
    _MODELOS_MULTI,
    _MODELOS_VALIDOS,
)
from api.core.rate_limit import limiter
from api.parsers import _detectar_anomalias, _fmt_csv, _parse_arquivo
from api.services.auth import TokenPayload, current_user
from api.services.conciliacao_llm import (
    chamar_modelo_async,
    friendly_anthropic_error,
    get_api_key,
    sintetizar_consenso,
)
from api.services.db_persistence import salvar_no_banco
from api.services.render import render_html
from api.services.storage import read_limited, salvar_dataset
from api.services.relatorio_local import _conciliacao_local

router = APIRouter(tags=["conciliacao"])
log = logging.getLogger("orgconc.conciliacao")

_SAFE_FILENAME_RE = re.compile(r"[^\w.\-]")


@router.post("/conciliar/ofx")
@limiter.limit("20/minute")
async def conciliar_ofx(
    request: Request,
    arquivos: List[UploadFile] = File(...),
    max_tokens: int = 16000,
    simular: bool = False,
    multi_modelo: bool = False,
    modelo: str = "sonnet",
    cliente_id: Optional[str] = None,
    user: TokenPayload = Depends(current_user),
):
    if modelo not in _MODELOS_VALIDOS:
        raise HTTPException(400, detail=f"modelo invalido: {modelo}")
    if not (100 <= max_tokens <= 64_000):
        raise HTTPException(400, detail="max_tokens deve estar entre 100 e 64000")
    if not (1 <= len(arquivos) <= 50):
        raise HTTPException(400, detail="Envie entre 1 e 50 arquivos")
    if cliente_id:
        try:
            uuid.UUID(cliente_id)
        except ValueError:
            raise HTTPException(400, detail="cliente_id invalido")

    extratos_parsed = []
    total_lido = 0
    for up in arquivos:
        content = await read_limited(up, MAX_UPLOAD_BYTES)
        total_lido += len(content)
        if total_lido > MAX_UPLOAD_TOTAL_BYTES:
            raise HTTPException(413, detail=f"Soma dos uploads excede {MAX_UPLOAD_TOTAL_MB} MB")
        safe_name = _SAFE_FILENAME_RE.sub("_", up.filename or "arquivo")[:64]
        try:
            txs = _parse_arquivo(content, up.filename)
        except HTTPException:
            raise
        except (ValueError, KeyError, UnicodeDecodeError) as exc:
            # parsers OFX/XML/PDF lancam diversos tipos; HTTPException ja
            # foi tratada acima. Demais erros viram 400 generico sem leak.
            log.exception("Falha parseando %s (%s)", safe_name, type(exc).__name__)
            raise HTTPException(400, detail="Falha ao parsear arquivo")
        if not txs:
            raise HTTPException(400, detail=f"Nao foi possivel extrair transacoes de {safe_name}")
        extratos_parsed.append({
            "arquivo": safe_name,
            "conta": txs[0]["conta"],
            "qtd": len(txs),
            "transacoes": txs,
        })

    if simular:
        anomalias = _detectar_anomalias(extratos_parsed)
        relatorio = _conciliacao_local(extratos_parsed, anomalias)
        rid = salvar_dataset(extratos_parsed, anomalias, relatorio, owner_sub=user.sub)
        db_status = await salvar_no_banco(rid, extratos_parsed, anomalias, "simulacao_local", cliente_id)
        return JSONResponse({
            "modo": "simulacao_local",
            "report_id": rid,
            "extratos": [{"arquivo": e["arquivo"], "conta": e["conta"], "qtd": e["qtd"]} for e in extratos_parsed],
            "anomalias": anomalias,
            "relatorio_md": relatorio,
            "relatorio_html": render_html(relatorio),
            "persistencia": db_status,
        })

    blocos = [
        f"=== {e['conta']} ({e['arquivo']}) ===\nTotal: {e['qtd']} transacoes\n{_fmt_csv(e['transacoes'])}"
        for e in extratos_parsed
    ]
    prompt = (
        f"Analise os {len(extratos_parsed)} extrato(s) bancario(s) abaixo. "
        "Identifique transferencias entre contas proprias, duplicidades, transacoes atipicas "
        "e pre-classifique para lancamento contabil. Gere relatorio em portugues em Markdown.\n\n"
        + "\n\n".join(blocos)
    )
    api_key = get_api_key()

    if multi_modelo:
        tokens_por_modelo = max(4000, max_tokens // 2)
        tarefas = [
            chamar_modelo_async(api_key, prompt, mid, label, tokens_por_modelo)
            for mid, label, _ in _MODELOS_MULTI
        ]
        raw = await asyncio.gather(*tarefas, return_exceptions=True)
        resultados = []
        for i, r in enumerate(raw):
            if isinstance(r, Exception):
                mid_label = _MODELOS_MULTI[i][1] if i < len(_MODELOS_MULTI) else "?"
                log.warning("Modelo %s falhou: %s", mid_label, r)
                resultados.append({
                    "texto": "", "input_tokens": 0, "output_tokens": 0,
                    "erro": str(r), "modelo": _MODELOS_MULTI[i][0], "label": mid_label,
                })
            else:
                resultados.append(r)
        relatorio_consolidado, score_consenso = await sintetizar_consenso(api_key, resultados, max_tokens)
        anomalias = _detectar_anomalias(extratos_parsed)
        rid = salvar_dataset(extratos_parsed, anomalias, relatorio_consolidado, owner_sub=user.sub)
        db_status = await salvar_no_banco(rid, extratos_parsed, anomalias, "multi_modelo", cliente_id)
        custo_total_usd = round(sum(r.get("cost_usd", 0.0) for r in resultados), 6)
        return JSONResponse({
            "modo": "multi_modelo",
            "report_id": rid,
            "score_consenso": score_consenso,
            "custo_total_usd": custo_total_usd,
            "modelos": [
                {
                    "modelo": r["modelo"],
                    "label": r["label"],
                    "input_tokens": r.get("input_tokens", 0),
                    "output_tokens": r.get("output_tokens", 0),
                    "cost_usd": r.get("cost_usd", 0.0),
                    "erro": r.get("erro"),
                }
                for r in resultados
            ],
            "extratos": [{"arquivo": e["arquivo"], "conta": e["conta"], "qtd": e["qtd"]} for e in extratos_parsed],
            "anomalias": anomalias,
            "relatorio_md": relatorio_consolidado,
            "relatorio_html": render_html(relatorio_consolidado),
            "relatorios_individuais": {r["label"]: r["texto"] for r in resultados if r["texto"]},
            "persistencia": db_status,
        })

    model_id, model_label = _MODELOS_VALIDOS[modelo]
    res = await chamar_modelo_async(api_key, prompt, model_id, model_label, max_tokens)
    if res.get("erro"):
        raise HTTPException(502, detail={"anthropic_error": friendly_anthropic_error(res["erro"])})
    relatorio = res["texto"]
    anomalias = _detectar_anomalias(extratos_parsed)
    rid = salvar_dataset(extratos_parsed, anomalias, relatorio, owner_sub=user.sub)
    db_status = await salvar_no_banco(rid, extratos_parsed, anomalias, "llm", cliente_id)
    return JSONResponse({
        "modo": "claude_llm",
        "modelo": modelo,
        "modelo_id": model_id,
        "modelo_label": model_label,
        "report_id": rid,
        "extratos": [{"arquivo": e["arquivo"], "conta": e["conta"], "qtd": e["qtd"]} for e in extratos_parsed],
        "anomalias": anomalias,
        "usage": {
            "input_tokens": res.get("input_tokens", 0),
            "output_tokens": res.get("output_tokens", 0),
            "cost_usd": res.get("cost_usd", 0.0),
        },
        "relatorio_md": relatorio,
        "relatorio_html": render_html(relatorio),
        "persistencia": db_status,
    })


@router.post("/conciliar/csv")
@limiter.limit("20/minute")
async def conciliar_csv(
    request: Request,
    extrato: UploadFile = File(...),
    razao: UploadFile = File(...),
    max_tokens: int = 16000,
    simular: bool = False,
    modelo: str = "sonnet",
    cliente_id: Optional[str] = None,
    user: TokenPayload = Depends(current_user),
):
    if modelo not in _MODELOS_VALIDOS:
        raise HTTPException(400, detail=f"modelo invalido: {modelo}")
    if cliente_id:
        try:
            uuid.UUID(cliente_id)
        except ValueError:
            raise HTTPException(400, detail="cliente_id invalido")

    extrato_bytes = await read_limited(extrato, MAX_UPLOAD_BYTES)
    razao_bytes = await read_limited(razao, MAX_UPLOAD_BYTES)
    extrato_text = extrato_bytes.decode("utf-8", errors="ignore")
    razao_text = razao_bytes.decode("utf-8", errors="ignore")

    safe_extrato = _SAFE_FILENAME_RE.sub("_", extrato.filename or "extrato.csv")[:64]
    safe_razao = _SAFE_FILENAME_RE.sub("_", razao.filename or "razao.csv")[:64]

    extratos_parsed = [{
        "arquivo": safe_extrato,
        "conta": f"CSV ({safe_extrato})",
        "qtd": max(1, extrato_text.count("\n") - 1),
        "transacoes": [],
    }]

    if simular:
        anomalias: list = []
        relatorio = (
            "# Relatório de Conciliação CSV\n\n"
            f"**Extrato:** {safe_extrato}\n**Razão:** {safe_razao}\n\n"
            "Modo simulação: envie arquivos OFX/PDF/XML para análise heurística completa.\n"
        )
        rid = salvar_dataset(extratos_parsed, anomalias, relatorio, owner_sub=user.sub)
        db_status = await salvar_no_banco(rid, extratos_parsed, anomalias, "simulacao_local", cliente_id)
        return JSONResponse({
            "modo": "simulacao_local_csv",
            "report_id": rid,
            "relatorio_md": relatorio,
            "relatorio_html": render_html(relatorio),
            "persistencia": db_status,
        })

    prompt = (
        "Realize a conciliacao bancaria entre o extrato e o razao contabil abaixo.\n\n"
        f"=== EXTRATO ({safe_extrato}) ===\n{extrato_text}\n\n"
        f"=== RAZAO ({safe_razao}) ===\n{razao_text}"
    )
    model_id, model_label = _MODELOS_VALIDOS[modelo]
    api_key = get_api_key()
    res = await chamar_modelo_async(api_key, prompt, model_id, model_label, max_tokens)
    if res.get("erro"):
        raise HTTPException(502, detail={"anthropic_error": friendly_anthropic_error(res["erro"])})
    relatorio = res["texto"]
    anomalias = []
    rid = salvar_dataset(extratos_parsed, anomalias, relatorio, owner_sub=user.sub)
    db_status = await salvar_no_banco(rid, extratos_parsed, anomalias, "llm_csv", cliente_id)
    return JSONResponse({
        "modo": "claude_llm_csv",
        "report_id": rid,
        "extrato": extrato.filename,
        "razao": razao.filename,
        "usage": {
            "input_tokens": res.get("input_tokens", 0),
            "output_tokens": res.get("output_tokens", 0),
            "cost_usd": res.get("cost_usd", 0.0),
        },
        "relatorio_md": relatorio,
        "relatorio_html": render_html(relatorio),
        "persistencia": db_status,
    })
