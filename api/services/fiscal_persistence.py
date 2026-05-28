"""Persistência de documentos fiscais e cruzamentos no PostgreSQL.

Sprint 1 do Plano de Integração Fiscal.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import (
    ConformidadeFornecedor,
    CruzamentoFiscal,
    DocumentoFiscal,
)
from api.matchers.cruzamento_fiscal import CruzamentoResult
from api.matchers.xml_fiscal import DocumentoFiscalLido

log = logging.getLogger("orgconc.fiscal.persistence")


def _parse_data(s: str) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


async def salvar_documentos_fiscais(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    documentos: Iterable[DocumentoFiscalLido],
) -> dict[str, uuid.UUID]:
    """Persiste documentos fiscais (deduplica por chave). Retorna map chave->id."""
    docs = list(documentos)
    if not docs:
        return {}

    # Carrega chaves já persistidas
    chaves = [d.chave for d in docs if d.chave]
    existentes_map: dict[str, uuid.UUID] = {}
    if chaves:
        stmt = select(DocumentoFiscal.chave, DocumentoFiscal.id).where(
            DocumentoFiscal.cliente_id == cliente_id,
            DocumentoFiscal.chave.in_(chaves),
        )
        for chave, row_id in (await db.execute(stmt)).all():
            existentes_map[chave] = row_id

    novos = 0
    for d in docs:
        if not d.chave or d.chave in existentes_map:
            continue
        novo = DocumentoFiscal(
            cliente_id=cliente_id,
            tipo=d.tipo,
            modelo=d.modelo or "55",
            chave=d.chave,
            numero=d.numero,
            serie=d.serie,
            data_emissao=_parse_data(d.data_emissao),
            emit_cnpj=d.emit_cnpj or None,
            emit_nome=d.emit_nome,
            emit_uf=d.emit_uf or None,
            dest_cnpj=d.dest_cnpj or None,
            dest_nome=d.dest_nome,
            valor_total=d.valor_total,
            valor_icms=d.valor_icms,
            valor_pis=d.valor_pis,
            valor_cofins=d.valor_cofins,
            valor_iss=d.valor_iss,
            natureza_operacao=d.natureza_operacao,
        )
        db.add(novo)
        existentes_map[d.chave] = novo.id
        novos += 1

    await db.flush()
    log.info(
        "fiscal.persistence: cliente=%s docs_recebidos=%d novos=%d existentes=%d",
        cliente_id, len(docs), novos, len(docs) - novos,
    )
    return existentes_map


async def salvar_cruzamentos(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    resultados: Iterable[CruzamentoResult],
    chave_para_id: dict[str, uuid.UUID],
) -> int:
    """Persiste cruzamentos. Retorna quantidade inserida.

    Observação: transacao_id permanece nulo nesta versão (o OFX é processado
    sem persistência das transações na conciliação fiscal stand-alone).
    """
    n = 0
    for r in resultados:
        doc_id = None
        if r.documento is not None:
            doc_id = chave_para_id.get(r.documento.chave)
        cruz = CruzamentoFiscal(
            cliente_id=cliente_id,
            documento_id=doc_id,
            transacao_id=None,
            status=r.status,
            diferenca_valor=r.diferenca_valor,
            diferenca_dias=r.diferenca_dias,
        )
        db.add(cruz)
        n += 1
    await db.flush()
    return n


async def listar_documentos_por_cliente(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    limit: int = 100,
) -> list[DocumentoFiscal]:
    stmt = (
        select(DocumentoFiscal)
        .where(DocumentoFiscal.cliente_id == cliente_id)
        .order_by(DocumentoFiscal.data_emissao.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def listar_cruzamentos(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    status: Optional[str] = None,
    limit: int = 500,
) -> list[CruzamentoFiscal]:
    stmt = select(CruzamentoFiscal).where(CruzamentoFiscal.cliente_id == cliente_id)
    if status:
        stmt = stmt.where(CruzamentoFiscal.status == status)
    stmt = stmt.order_by(CruzamentoFiscal.criado_em.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def salvar_conformidade(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    cnpj_fornecedor: str,
    payload: dict,
) -> ConformidadeFornecedor:
    """Upsert simples por (cliente_id, cnpj_fornecedor).

    Sprint 4: dispara notificação fiscal quando classe muda para CRITICO.
    """
    stmt = select(ConformidadeFornecedor).where(
        ConformidadeFornecedor.cliente_id == cliente_id,
        ConformidadeFornecedor.cnpj_fornecedor == cnpj_fornecedor,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    classe_anterior = existing.risco_classe if existing else None
    classe_nova = payload.get("risco_classe")

    if existing:
        for k, v in payload.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        existing.atualizado_em = datetime.utcnow()
        await db.flush()
        resultado = existing
    else:
        novo = ConformidadeFornecedor(
            cliente_id=cliente_id,
            cnpj_fornecedor=cnpj_fornecedor,
            **payload,
        )
        db.add(novo)
        await db.flush()
        resultado = novo

    # Sprint 4: notifica se houve transição para CRITICO
    if classe_nova == "CRITICO" and classe_anterior != "CRITICO":
        try:
            from api.services.fiscal_notifications import notificar_classe_critica
            flags_str = payload.get("flags") or ""
            flags_list = [f for f in flags_str.split(",") if f] if flags_str else []
            await notificar_classe_critica(
                db,
                cliente_id=cliente_id,
                cnpj_fornecedor=cnpj_fornecedor,
                razao_social=payload.get("razao_social", ""),
                risco_anual=float(payload.get("risco_tributario_anual", 0) or 0),
                flags=flags_list,
                classe_anterior=classe_anterior,
            )
        except Exception:
            log.exception("Falha ao notificar transição CRITICO para %s", cnpj_fornecedor)

    return resultado


async def listar_conformidade(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    classe_minima: Optional[str] = None,
) -> list[ConformidadeFornecedor]:
    stmt = select(ConformidadeFornecedor).where(
        ConformidadeFornecedor.cliente_id == cliente_id
    )
    if classe_minima:
        ordem = {"BAIXO": 0, "MEDIO": 1, "ALTO": 2, "CRITICO": 3}
        min_ord = ordem.get(classe_minima, 0)
        validas = [c for c, o in ordem.items() if o >= min_ord]
        stmt = stmt.where(ConformidadeFornecedor.risco_classe.in_(validas))
    stmt = stmt.order_by(ConformidadeFornecedor.risco_tributario_anual.desc())
    return list((await db.execute(stmt)).scalars().all())
