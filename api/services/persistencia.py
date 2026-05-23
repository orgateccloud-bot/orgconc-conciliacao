"""Persistencia JSON em disco e PostgreSQL."""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date
from typing import Optional

from fastapi import HTTPException, UploadFile
from markdown import markdown as md_to_html

from api.core.config import DATA_DIR, DB_DISPONIVEL, SessionLocal, log, models
from api.core.templates import LOGO_DATA_URI, jinja_env
from api.parsers import _chave_transacao, _classificar, _coletar_chaves_anomalas
from api.services.sanitize import sanitize_html

logger = logging.getLogger("orgconc.persistencia")


async def read_limited(up: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await up.read(1024 * 256)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Arquivo {up.filename} excede limite de upload",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def salvar_dataset(extratos: list[dict], anomalias: list[dict], relatorio: str) -> str:
    rid = uuid.uuid4().hex[:12]
    path = DATA_DIR / f"{rid}.json"
    payload = {"extratos": extratos, "anomalias": anomalias, "relatorio": relatorio}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    existing = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in existing[50:]:
        try:
            old.unlink()
        except OSError:
            pass
    log.info("Dataset salvo: %s", rid)
    return rid


def carregar_dataset(rid: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{12}", rid):
        raise HTTPException(status_code=400, detail="ID invalido")
    path = DATA_DIR / f"{rid}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado ou expirado")
    return json.loads(path.read_text(encoding="utf-8"))


async def salvar_no_banco(
    report_id: str,
    extratos: list[dict],
    anomalias: list[dict],
    modo: str,
    cliente_id: Optional[str] = None,
) -> dict:
    if not DB_DISPONIVEL:
        return {"status": "skip", "motivo": "db_indisponivel"}
    try:
        total_cred = sum(t["valor"] for e in extratos for t in e["transacoes"] if t["valor"] > 0)
        total_deb = sum(t["valor"] for e in extratos for t in e["transacoes"] if t["valor"] < 0)
        datas = sorted({t["data"] for e in extratos for t in e["transacoes"] if t.get("data")})
        cid = uuid.UUID(cliente_id) if cliente_id else None
        async with SessionLocal() as db:
            async with db.begin():
                conc = models.Conciliacao(
                    cliente_id=cid,
                    report_id=report_id,
                    modo=modo,
                    total_transacoes=sum(e["qtd"] for e in extratos),
                    total_anomalias=len(anomalias),
                    valor_total_credito=total_cred,
                    valor_total_debito=total_deb,
                    periodo_inicio=date.fromisoformat(datas[0]) if datas else None,
                    periodo_fim=date.fromisoformat(datas[-1]) if datas else None,
                )
                db.add(conc)
                await db.flush()
                chaves_anomalas = _coletar_chaves_anomalas(extratos)
                txs = [
                    models.Transacao(
                        conciliacao_id=conc.id,
                        cliente_id=cid,
                        data_lancamento=date.fromisoformat(t["data"]) if t.get("data") else date.today(),
                        valor=t["valor"],
                        memo=t.get("memo"),
                        categoria=_classificar(t.get("memo", ""), t.get("nome", "")),
                        banco=e.get("conta"),
                        tipo=t.get("tipo"),
                        eh_anomalia=_chave_transacao(e.get("conta", ""), t) in chaves_anomalas,
                    )
                    for e in extratos for t in e["transacoes"]
                ]
                db.add_all(txs)
            log.info("Conciliacao %s salva no banco (%d transacoes)", report_id, len(txs))
        return {"status": "ok", "transacoes_persistidas": len(txs)}
    except Exception as exc:
        log.exception("Falha ao salvar no banco (conciliacao %s)", report_id)
        return {"status": "error", "erro": type(exc).__name__, "mensagem": str(exc)[:200]}


def render_html(relatorio_md: str) -> str:
    from datetime import datetime
    body = md_to_html(relatorio_md, extensions=["tables", "fenced_code"])
    body = sanitize_html(body)
    return jinja_env.get_template("relatorio.html").render(
        body=body,
        agora=datetime.now().strftime("%d/%m/%Y %H:%M"),
        logo_data_uri=LOGO_DATA_URI,
    )


def render_pdf_html(relatorio_md: str, anomalias: list, extratos: list, report_id: str) -> str:
    from datetime import datetime
    body = md_to_html(relatorio_md, extensions=["tables", "fenced_code"])
    body = sanitize_html(body)
    total_tx = sum(e.get("qtd", 0) for e in extratos)
    total_cred = sum(t["valor"] for e in extratos for t in e.get("transacoes", []) if t["valor"] > 0)
    total_deb = sum(t["valor"] for e in extratos for t in e.get("transacoes", []) if t["valor"] < 0)
    n_crit = sum(1 for a in anomalias if a.get("severidade") == "critico")
    n_alerta = sum(1 for a in anomalias if a.get("severidade") == "alerta")
    n_atenc = sum(1 for a in anomalias if a.get("severidade") == "atencao")
    return jinja_env.get_template("relatorio_pdf.html").render(
        report_id=report_id,
        agora=datetime.now().strftime("%d/%m/%Y %H:%M"),
        body=body,
        anomalias=anomalias,
        n_anom=len(anomalias),
        n_crit=n_crit,
        n_alerta=n_alerta,
        n_atenc=n_atenc,
        total_tx=total_tx,
        total_cred=total_cred,
        total_deb_abs=abs(total_deb),
        n_contas=len(extratos),
        logo_data_uri=LOGO_DATA_URI,
    )
