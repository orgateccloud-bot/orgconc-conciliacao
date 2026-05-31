from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
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

# UUID v1-v5 canonico: cliente_id invalido -> 422 (validacao FastAPI/Query)
_UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

# Sinonimos de cabecalho aceitos no parser de CSV estruturado
_CSV_DATA_KEYS = ("data", "date", "dt", "data_lancamento", "datalancamento")
_CSV_MEMO_KEYS = (
    "descricao", "descrição", "memo", "historico", "histórico",
    "detalhe", "descricao_operacao", "obs",
)
_CSV_VALOR_KEYS = ("valor", "value", "amount", "montante", "vlr", "valor_brl")
_CSV_TIPO_KEYS = ("tipo", "type", "operacao", "operação", "natureza")
_CSV_NOME_KEYS = ("nome", "name", "contraparte", "favorecido", "beneficiario")

# Regex auxiliares para parser por linha (CSV sem cabecalho ou formato livre)
_RX_DATA_BR = re.compile(r"\b(\d{2})/(\d{2})/(\d{2,4})\b")
_RX_DATA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_RX_VALOR = re.compile(r"(-?\(?\s*R?\$?\s*[\d.]+,\d{2}\)?|-?\d+\.\d{2})")


def _parse_valor_csv(s: str) -> Optional[float]:
    """Converte valor monetario BR/EN para float (negativo se entre parenteses)."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    neg = (s.startswith("(") and s.endswith(")")) or s.startswith("-")
    s = s.strip("()").replace("R$", "").replace("$", "").replace(" ", "")
    s = s.lstrip("+-")
    if "," in s and "." in s:
        # formato BR: 1.234,56 — remove . de milhar
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def _parse_data_csv(s: str) -> Optional[str]:
    """Converte data BR (dd/mm/aaaa) ou ISO (aaaa-mm-dd) para ISO."""
    if not s:
        return None
    s = str(s).strip()
    m = _RX_DATA_ISO.search(s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _RX_DATA_BR.search(s)
    if m:
        dia, mes, ano = m.groups()
        if len(ano) == 2:
            ano = "20" + ano
        return f"{ano}-{mes}-{dia}"
    return None


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    """Retorna primeiro valor nao-vazio entre `keys` (case-insensitive)."""
    norm = {(k or "").strip().lower(): v for k, v in row.items()}
    for k in keys:
        if k in norm and norm[k] not in (None, ""):
            return str(norm[k]).strip()
    return ""


def _parse_csv_text(text: str, conta_label: str) -> list[dict]:
    """Parser CSV estruturado — detecta cabecalho e mapeia colunas.

    Aceita variacoes de separador (`,` / `;` / `\t`), cabecalhos pt/en
    e valores em formato BR (1.234,56) ou EN (1234.56).
    """
    if not text or not text.strip():
        return []
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        class _D(csv.excel):
            delimiter = ","
        dialect = _D()

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    transacoes: list[dict] = []

    # Se DictReader nao detectou cabecalhos validos (todos None/vazios),
    # caimos para parser por regex de linha.
    if not reader.fieldnames or all(not (f or "").strip() for f in reader.fieldnames):
        return _parse_csv_freeform(text, conta_label)

    headers_norm = {(f or "").strip().lower() for f in reader.fieldnames}
    tem_data = any(h in headers_norm for h in _CSV_DATA_KEYS)
    tem_valor = any(h in headers_norm for h in _CSV_VALOR_KEYS)

    # Se cabecalho nao tem campos esperados, usa parser livre
    if not (tem_data and tem_valor):
        return _parse_csv_freeform(text, conta_label)

    for row in reader:
        data_iso = _parse_data_csv(_pick(row, _CSV_DATA_KEYS))
        valor = _parse_valor_csv(_pick(row, _CSV_VALOR_KEYS))
        if not data_iso or valor is None:
            continue
        memo = _pick(row, _CSV_MEMO_KEYS)
        nome = _pick(row, _CSV_NOME_KEYS)
        tipo_raw = _pick(row, _CSV_TIPO_KEYS).upper()
        if tipo_raw in ("D", "DEBIT", "DEBITO", "DÉBITO"):
            valor = -abs(valor)
        elif tipo_raw in ("C", "CREDIT", "CREDITO", "CRÉDITO"):
            valor = abs(valor)
        transacoes.append({
            "conta": conta_label,
            "data": data_iso,
            "tipo": "CREDIT" if valor > 0 else "DEBIT",
            "valor": valor,
            "memo": memo,
            "nome": nome,
            "checknum": "",
        })
    return transacoes


def _parse_csv_freeform(text: str, conta_label: str) -> list[dict]:
    """Fallback: extrai data+valor de cada linha (sem cabecalho confiavel)."""
    transacoes: list[dict] = []
    for linha in text.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        data_iso = _parse_data_csv(linha)
        m_val = _RX_VALOR.search(linha)
        if not data_iso or not m_val:
            continue
        valor = _parse_valor_csv(m_val.group(1))
        if valor is None:
            continue
        # memo = linha sem data e sem valor
        memo = _RX_DATA_BR.sub("", _RX_DATA_ISO.sub("", linha))
        memo = _RX_VALOR.sub("", memo).strip(" ,;|\t")
        transacoes.append({
            "conta": conta_label,
            "data": data_iso,
            "tipo": "CREDIT" if valor > 0 else "DEBIT",
            "valor": valor,
            "memo": memo[:120],
            "nome": "",
            "checknum": "",
        })
    return transacoes


@router.post("/conciliar/ofx")
@limiter.limit("20/minute")
async def conciliar_ofx(
    request: Request,
    arquivos: List[UploadFile] = File(...),
    max_tokens: int = Query(default=16000, ge=100, le=64000),
    simular: bool = False,
    multi_modelo: bool = False,
    modelo: str = "sonnet",
    cliente_id: Optional[str] = Query(default=None, pattern=_UUID_PATTERN),
    user: TokenPayload = Depends(current_user),
):
    if modelo not in _MODELOS_VALIDOS:
        raise HTTPException(400, detail=f"modelo invalido: {modelo}")
    if not (1 <= len(arquivos) <= 50):
        raise HTTPException(400, detail="Envie entre 1 e 50 arquivos")

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
                    "truncado": r.get("truncado", False),
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
        status = res.get("status_code") or 502
        raise HTTPException(status, detail={"anthropic_error": friendly_anthropic_error(res["erro"])})
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
            "truncado": res.get("truncado", False),
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
    max_tokens: int = Query(default=16000, ge=1, le=32768),
    simular: bool = False,
    modelo: str = "sonnet",
    cliente_id: Optional[str] = Query(default=None, pattern=_UUID_PATTERN),
    user: TokenPayload = Depends(current_user),
):
    if modelo not in _MODELOS_VALIDOS:
        raise HTTPException(400, detail=f"modelo invalido: {modelo}")

    extrato_bytes = await read_limited(extrato, MAX_UPLOAD_BYTES)
    razao_bytes = await read_limited(razao, MAX_UPLOAD_BYTES)
    extrato_text = extrato_bytes.decode("utf-8", errors="ignore")
    razao_text = razao_bytes.decode("utf-8", errors="ignore")

    safe_extrato = _SAFE_FILENAME_RE.sub("_", extrato.filename or "extrato.csv")[:64]
    safe_razao = _SAFE_FILENAME_RE.sub("_", razao.filename or "razao.csv")[:64]

    conta_label = f"CSV ({safe_extrato})"
    transacoes_csv = _parse_csv_text(extrato_text, conta_label)
    extratos_parsed = [{
        "arquivo": safe_extrato,
        "conta": conta_label,
        "qtd": len(transacoes_csv) or max(1, extrato_text.count("\n") - 1),
        "transacoes": transacoes_csv,
    }]

    if simular:
        # Parser estruturado: detecta anomalias mesmo no modo simulacao CSV
        anomalias = _detectar_anomalias(extratos_parsed) if transacoes_csv else []
        if transacoes_csv:
            cred = sum(t["valor"] for t in transacoes_csv if t["valor"] > 0)
            deb = sum(t["valor"] for t in transacoes_csv if t["valor"] < 0)
            relatorio = (
                "# Relatório de Conciliação CSV\n\n"
                f"**Extrato:** {safe_extrato}\n**Razão:** {safe_razao}\n\n"
                f"## Resumo\n\n"
                f"- Transações extraídas: **{len(transacoes_csv)}**\n"
                f"- Créditos: **R$ {cred:,.2f}**\n"
                f"- Débitos: **R$ {deb:,.2f}**\n"
                f"- Saldo do período: **R$ {cred + deb:,.2f}**\n"
                f"- Anomalias detectadas: **{len(anomalias)}**\n\n"
                "Modo simulação local: heurística aplicada ao CSV estruturado. "
                "Para análise com LLM, repita sem `simular=true`.\n"
            )
        else:
            relatorio = (
                "# Relatório de Conciliação CSV\n\n"
                f"**Extrato:** {safe_extrato}\n**Razão:** {safe_razao}\n\n"
                "Nenhuma transação reconhecida no CSV (cabeçalhos esperados: "
                "`data`, `descricao`/`memo`, `valor`). "
                "Envie arquivos OFX/PDF/XML para análise heurística completa.\n"
            )
        rid = salvar_dataset(extratos_parsed, anomalias, relatorio, owner_sub=user.sub)
        db_status = await salvar_no_banco(rid, extratos_parsed, anomalias, "simulacao_local", cliente_id)
        return JSONResponse({
            "modo": "simulacao_local_csv",
            "report_id": rid,
            "extratos": [{"arquivo": e["arquivo"], "conta": e["conta"], "qtd": e["qtd"]} for e in extratos_parsed],
            "anomalias": anomalias,
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
        status = res.get("status_code") or 502
        raise HTTPException(status, detail={"anthropic_error": friendly_anthropic_error(res["erro"])})
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
