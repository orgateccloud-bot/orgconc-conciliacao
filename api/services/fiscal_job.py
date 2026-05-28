"""Job assíncrono mensal de detecção de gaps fiscais.

Sprint 4 do Plano de Integração Fiscal.

Executa para cada cliente:
1. Lista documentos fiscais persistidos do último período
2. Lista transações OFX disponíveis
3. Recalcula conformidade + risco tributário
4. Compara classes antes/depois e dispara notificações para mudanças CRITICO

Pode ser invocado via:
- Cron externo (preferido em produção): rodar `python -m api.services.fiscal_job`
- Task assíncrona interna no FastAPI startup (fallback dev)

Atualmente é um stub funcional — em produção pode ser plugado em Celery/RQ.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Cliente, ConformidadeFornecedor, DocumentoFiscal

log = logging.getLogger("orgconc.fiscal.job")


async def listar_clientes_ativos(db: AsyncSession) -> list[Cliente]:
    stmt = select(Cliente).where(Cliente.ativo == True)  # noqa: E712
    return list((await db.execute(stmt)).scalars().all())


async def detectar_mudancas_classe(
    db: AsyncSession,
    cliente_id,
    novas_scores: list[dict],
) -> list[dict]:
    """Compara classe atual no banco com a nova classe calculada.

    Retorna lista de mudanças onde a classe nova é CRITICO e a anterior era diferente.
    """
    cnpjs = [s["cnpj_fornecedor"] for s in novas_scores]
    if not cnpjs:
        return []
    stmt = select(
        ConformidadeFornecedor.cnpj_fornecedor,
        ConformidadeFornecedor.risco_classe,
    ).where(
        ConformidadeFornecedor.cliente_id == cliente_id,
        ConformidadeFornecedor.cnpj_fornecedor.in_(cnpjs),
    )
    anteriores = {cnpj: classe for cnpj, classe in (await db.execute(stmt)).all()}

    mudancas: list[dict] = []
    for s in novas_scores:
        cnpj = s["cnpj_fornecedor"]
        classe_anterior = anteriores.get(cnpj)
        if s["risco_classe"] == "CRITICO" and classe_anterior != "CRITICO":
            mudancas.append({**s, "classe_anterior": classe_anterior})
    return mudancas


async def rodar_para_cliente(
    db: AsyncSession,
    cliente: Cliente,
    janela_dias: int = 30,
) -> dict:
    """Roda análise fiscal para um cliente. Retorna estatísticas."""
    log.info("fiscal.job: iniciando cliente=%s nome=%s", cliente.id, cliente.nome)

    fim = date.today()
    inicio = fim - timedelta(days=janela_dias)
    stmt = select(DocumentoFiscal).where(
        DocumentoFiscal.cliente_id == cliente.id,
        DocumentoFiscal.data_emissao >= inicio,
        DocumentoFiscal.data_emissao <= fim,
    )
    docs = list((await db.execute(stmt)).scalars().all())

    return {
        "cliente_id": str(cliente.id),
        "documentos_encontrados": len(docs),
        "janela_dias": janela_dias,
        "executado_em": datetime.utcnow().isoformat(),
    }


async def rodar_job_completo(janela_dias: int = 30) -> dict:
    """Executa o job para todos os clientes ativos.

    Para ser plugado em Celery: simplesmente envolver em `@shared_task`.
    """
    from api.core.config import DB_DISPONIVEL, SessionLocal

    if not DB_DISPONIVEL:
        log.warning("fiscal.job: DB indisponível, abortando")
        return {"executado": False, "motivo": "db_indisponivel"}

    resultados = []
    async with SessionLocal() as db:
        clientes = await listar_clientes_ativos(db)
        log.info("fiscal.job: processando %d clientes ativos", len(clientes))
        for cliente in clientes:
            try:
                resultado = await rodar_para_cliente(db, cliente, janela_dias)
                resultados.append(resultado)
            except Exception as exc:
                log.exception("fiscal.job: falha cliente=%s: %s", cliente.id, exc)

    return {
        "executado": True,
        "clientes_processados": len(resultados),
        "janela_dias": janela_dias,
        "resultados": resultados,
    }


if __name__ == "__main__":
    # Modo standalone: python -m api.services.fiscal_job
    logging.basicConfig(level=logging.INFO)
    resultado = asyncio.run(rodar_job_completo())
    print(resultado)
