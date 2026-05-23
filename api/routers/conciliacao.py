from __future__ import annotations

import asyncio
import logging
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
from api.services.auth import current_user
from api.services.conciliacao_llm import (
    chamar_modelo_async,
    friendly_anthropic_error,
    get_api_key,
    sintetizar_consenso,
)
from api.services.persistencia import (
    read_limited,
    render_html,
    salvar_dataset,
    salvar_no_banco,
)
from api.services.relatorio_local import _conciliacao_local

router = APIRouter(tags=["conciliacao"], dependencies=[Depends(current_user)])
log = logging.getLogger("orgconc.conciliacao")


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
):
    if modelo not in _MODELOS_VALIDOS:
        raise HTTPException(400, detail=f"modelo invalido: {modelo}")
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
        try:
            txs = _parse_arquivo(content, up.filename)
        except HTTPException:
            raise
        except Exception:
            log.exception("Falha parseando %s", up.filename)
            raise HTTPException(400, detail=f"Falha ao parsear {up.filename}")
        if not txs:
            raise HTTPException(400, detail=f"Nao foi possivel extrair transacoes de {up.filename}")
        extratos_parsed.append({
            "arquivo": up.filename,
            "conta": txs[0]["conta"],
            "qtd": len(txs),
            "transacoes": txs,
        })

    if simular:
        anomalias = _detectar_anomalias(extratos_parsed)
        relatorio = _conciliacao_local(extratos_parsed, anomalias)
        rid = salvar_dataset(extratos_parsed, anomalias, relatorio)
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
        resultados = list(await asyncio.gather(*tarefas))
        relatorio_consolidado, score_consenso = await sintetizar_consenso(api_key, resultados, max_tokens)
        anomalias = _detectar_anomalias(extratos_parsed)
        rid = salvar_dataset(extratos_parsed, anomalias, relatorio_consolidado)
        db_status = await salvar_no_banco(rid, extratos_parsed, anomalias, "multi_modelo", cliente_id)
        return JSONResponse({
            "modo": "multi_modelo",
            "report_id": rid,
            "score_consenso": score_consenso,
            "modelos": [
                {
                    "modelo": r["modelo"],
                    "label": r["label"],
                    "input_tokens": r.get("input_tokens", 0),
                    "output_tokens": r.get("output_tokens", 0),
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
    rid = salvar_dataset(extratos_parsed, anomalias, relatorio)
    db_status = await salvar_no_banco(rid, extratos_parsed, anomalias, "llm", cliente_id)
    return JSONResponse({
        "modo": "claude_llm",
        "modelo": modelo,
        "modelo_id": model_id,
        "modelo_label": model_label,
        "report_id": rid,
        "extratos": [{"arquivo": e["arquivo"], "conta": e["conta"], "qtd": e["qtd"]} for e in extratos_parsed],
        "anomalias": anomalias,
        "usage": {"input_tokens": res.get("input_tokens", 0), "output_tokens": res.get("output_tokens", 0)},
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

    extratos_parsed = [{
        "arquivo": extrato.filename or "extrato.csv",
        "conta": f"CSV ({extrato.filename})",
        "qtd": max(1, extrato_text.count("\n") - 1),
        "transacoes": [],
    }]

    if simular:
        anomalias: list = []
        relatorio = (
            "# Relatório de Conciliação CSV\n\n"
            f"**Extrato:** {extrato.filename}\n**Razão:** {razao.filename}\n\n"
            "Modo simulação: envie arquivos OFX/PDF/XML para análise heurística completa.\n"
        )
        rid = salvar_dataset(extratos_parsed, anomalias, relatorio)
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
        f"=== EXTRATO ({extrato.filename}) ===\n{extrato_text}\n\n"
        f"=== RAZAO ({razao.filename}) ===\n{razao_text}"
    )
    model_id, model_label = _MODELOS_VALIDOS[modelo]
    api_key = get_api_key()
    res = await chamar_modelo_async(api_key, prompt, model_id, model_label, max_tokens)
    if res.get("erro"):
        raise HTTPException(502, detail={"anthropic_error": friendly_anthropic_error(res["erro"])})
    relatorio = res["texto"]
    anomalias = []
    rid = salvar_dataset(extratos_parsed, anomalias, relatorio)
    db_status = await salvar_no_banco(rid, extratos_parsed, anomalias, "llm_csv", cliente_id)
    return JSONResponse({
        "modo": "claude_llm_csv",
        "report_id": rid,
        "extrato": extrato.filename,
        "razao": razao.filename,
        "usage": {"input_tokens": res.get("input_tokens", 0), "output_tokens": res.get("output_tokens", 0)},
        "relatorio_md": relatorio,
        "relatorio_html": render_html(relatorio),
        "persistencia": db_status,
    })
