"""Implementacao SQLAlchemy do ConciliacaoRepository."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Conciliacao as ConciliacaoOrm
from api.domain.entities import Conciliacao


def _to_entity(row: ConciliacaoOrm) -> Conciliacao:
    return Conciliacao(
        id=row.id,
        report_id=row.report_id,
        modo=row.modo,
        total_transacoes=row.total_transacoes,
        total_anomalias=row.total_anomalias,
        cliente_id=row.cliente_id,
        valor_total_credito=row.valor_total_credito,
        valor_total_debito=row.valor_total_debito,
        periodo_inicio=row.periodo_inicio,
        periodo_fim=row.periodo_fim,
        criado_em=row.criado_em,
    )


class ConciliacaoRepositorySQL:
    def __init__(self, session: AsyncSession):
        self._db = session

    async def salvar(self, conciliacao: Conciliacao) -> Conciliacao:
        orm = ConciliacaoOrm(
            cliente_id=conciliacao.cliente_id,
            report_id=conciliacao.report_id,
            modo=conciliacao.modo,
            total_transacoes=conciliacao.total_transacoes,
            total_anomalias=conciliacao.total_anomalias,
            valor_total_credito=conciliacao.valor_total_credito,
            valor_total_debito=conciliacao.valor_total_debito,
            periodo_inicio=conciliacao.periodo_inicio,
            periodo_fim=conciliacao.periodo_fim,
        )
        self._db.add(orm)
        await self._db.commit()
        await self._db.refresh(orm)
        return _to_entity(orm)

    async def listar(
        self,
        *,
        cliente_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conciliacao]:
        q = (
            select(ConciliacaoOrm)
            .order_by(ConciliacaoOrm.criado_em.desc())
            .limit(min(limit, 100))
            .offset(offset)
        )
        if cliente_id:
            q = q.where(ConciliacaoOrm.cliente_id == cliente_id)
        result = await self._db.execute(q)
        return [_to_entity(r) for r in result.scalars().all()]

    async def buscar_por_report_id(self, report_id: str) -> Conciliacao | None:
        result = await self._db.execute(
            select(ConciliacaoOrm).where(ConciliacaoOrm.report_id == report_id)
        )
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None
