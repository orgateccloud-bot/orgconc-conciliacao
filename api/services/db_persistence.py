"""Persistencia de conciliacoes no banco PostgreSQL."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from api.core.config import DB_DISPONIVEL, SessionLocal, log, models
from api.parsers import _chave_transacao, _classificar, _coletar_chaves_anomalas


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

        # Pre-calcular tudo fora da sessao para garantir atomicidade:
        # se qualquer calculo falhar, o banco nao e tocado.
        chaves_anomalas = _coletar_chaves_anomalas(extratos)
        txs_data = [
            {
                "cliente_id": cid,
                "data_lancamento": date.fromisoformat(t["data"]) if t.get("data") else date.today(),
                "valor": t["valor"],
                "memo": t.get("memo"),
                "categoria": _classificar(t.get("memo", ""), t.get("nome", "")),
                "banco": e.get("conta"),
                "tipo": t.get("tipo"),
                "eh_anomalia": _chave_transacao(e.get("conta", ""), t) in chaves_anomalas,
            }
            for e in extratos for t in e["transacoes"]
        ]

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
                await db.flush()  # gera conc.id
                txs = [models.Transacao(conciliacao_id=conc.id, **td) for td in txs_data]
                db.add_all(txs)
            log.info("Conciliacao %s salva no banco (%d transacoes)", report_id, len(txs))
        return {"status": "ok", "transacoes_persistidas": len(txs)}
    except Exception as exc:
        log.exception("Falha ao salvar no banco (conciliacao %s)", report_id)
        return {"status": "error", "erro": type(exc).__name__, "mensagem": str(exc)[:200]}
