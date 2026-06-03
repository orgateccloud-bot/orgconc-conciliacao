"""Persistência de documentos fiscais e cruzamentos no PostgreSQL.

Sprint 1 do Plano de Integração Fiscal.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import (
    ApuracaoCBSIBS,
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
    """Persiste documentos fiscais (deduplica por chave). Retorna map chave->id.

    F-03: usa bulk insert via `insert().values([...]).returning(...)` para reduzir
    de N roundtrips a 1 quando ha muitos documentos novos.
    """
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

    # Monta lista de novos (deduplica chaves repetidas no proprio lote)
    chaves_no_lote: set[str] = set()
    novos_dicts: list[dict] = []
    for d in docs:
        if not d.chave or d.chave in existentes_map or d.chave in chaves_no_lote:
            continue
        chaves_no_lote.add(d.chave)
        novos_dicts.append({
            "id": uuid.uuid4(),
            "cliente_id": cliente_id,
            "tipo": d.tipo,
            "modelo": d.modelo or "55",
            "chave": d.chave,
            "numero": d.numero,
            "serie": d.serie,
            "data_emissao": _parse_data(d.data_emissao),
            "emit_cnpj": d.emit_cnpj or None,
            "emit_nome": d.emit_nome,
            "emit_uf": d.emit_uf or None,
            "dest_cnpj": d.dest_cnpj or None,
            "dest_nome": d.dest_nome,
            "valor_total": d.valor_total,
            "valor_icms": d.valor_icms,
            "valor_pis": d.valor_pis,
            "valor_cofins": d.valor_cofins,
            "valor_iss": d.valor_iss,
            "natureza_operacao": d.natureza_operacao,
        })

    if novos_dicts:
        # Bulk insert em lotes de 500 (Postgres tem limite de parametros)
        BATCH = 500
        for i in range(0, len(novos_dicts), BATCH):
            chunk = novos_dicts[i:i + BATCH]
            await db.execute(insert(DocumentoFiscal), chunk)
        for d in novos_dicts:
            existentes_map[d["chave"]] = d["id"]
        await db.flush()

    log.info(
        "fiscal.persistence: cliente=%s docs_recebidos=%d novos=%d existentes=%d",
        cliente_id, len(docs), len(novos_dicts), len(docs) - len(novos_dicts),
    )
    return existentes_map


async def salvar_cruzamentos(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    resultados: Iterable[CruzamentoResult],
    chave_para_id: dict[str, uuid.UUID],
) -> int:
    """Persiste cruzamentos. Retorna quantidade inserida.

    F-03: bulk insert em lotes de 500 (Postgres parameter limit).
    Observação: transacao_id permanece nulo nesta versão (o OFX é processado
    sem persistência das transações na conciliação fiscal stand-alone).
    """
    payload: list[dict] = []
    for r in resultados:
        doc_id = None
        if r.documento is not None:
            doc_id = chave_para_id.get(r.documento.chave)
        payload.append({
            "id": uuid.uuid4(),
            "cliente_id": cliente_id,
            "documento_id": doc_id,
            "transacao_id": None,
            "status": r.status,
            "diferenca_valor": r.diferenca_valor,
            "diferenca_dias": r.diferenca_dias,
        })

    if not payload:
        return 0

    BATCH = 500
    for i in range(0, len(payload), BATCH):
        chunk = payload[i:i + BATCH]
        await db.execute(insert(CruzamentoFiscal), chunk)
    await db.flush()
    return len(payload)


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
        existing.atualizado_em = datetime.now(timezone.utc)
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


async def salvar_apuracao(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    documento_id: uuid.UUID,
    payload: dict,
) -> ApuracaoCBSIBS:
    """Upsert da apuração CBS/IBS por (documento_id, versao_base) — idempotente (IC-02 §3/§4).

    `payload` deve conter ao menos `versao_base` e `ambiente`; demais campos
    (valores/alíquotas por esfera, v_tot_trib, memoria_calculo, itens, etc.) são
    opcionais. O cálculo é responsabilidade da Calculadora (fronteira IC-02 §1.3);
    esta função apenas persiste o resultado já apurado.
    """
    versao_base = payload.get("versao_base")
    stmt = select(ApuracaoCBSIBS).where(
        ApuracaoCBSIBS.documento_id == documento_id,
        ApuracaoCBSIBS.versao_base == versao_base,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        for k, v in payload.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        existing.obtido_em = datetime.now(timezone.utc)
        await db.flush()
        return existing

    novo = ApuracaoCBSIBS(cliente_id=cliente_id, documento_id=documento_id, **payload)
    db.add(novo)
    await db.flush()
    return novo


async def listar_apuracao(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    documento_id: Optional[uuid.UUID] = None,
    limit: int = 500,
) -> list[ApuracaoCBSIBS]:
    stmt = select(ApuracaoCBSIBS).where(ApuracaoCBSIBS.cliente_id == cliente_id)
    if documento_id:
        stmt = stmt.where(ApuracaoCBSIBS.documento_id == documento_id)
    stmt = stmt.order_by(ApuracaoCBSIBS.obtido_em.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())
