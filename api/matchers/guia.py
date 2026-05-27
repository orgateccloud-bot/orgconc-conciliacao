"""Matcher do estágio 4 — casa transações contra guias tributárias cadastradas.

Porta de `D:\\00_Inbox\\OrgNeural2\\match_guia.py` para SQLAlchemy async.
Critério: mesmo cliente + valor coincidente (±R$0.01). Desempata pelo tipo
(DARF/DAS/GPS/GNRE) extraído pela cascata.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import GuiaTributo
from api.matchers.cascata import Resultado

TOLERANCIA_VALOR = Decimal("0.01")


@dataclass
class GuiaResolvida:
    resultado: Resultado
    status: str           # RESOLVIDO / GUIA_NAO_ENCONTRADA / GUIA_AMBIGUA
    tipo: str = ""
    competencia: str = ""
    conta_contabil: str = ""
    flag: str = ""


async def resolver(
    resultados: list[Resultado],
    db: AsyncSession,
    cliente_id: uuid.UUID,
) -> list[GuiaResolvida]:
    """Casa transações do estágio 4 (match_guia_tributo) contra cadastro."""
    alvo = [r for r in resultados if r.metodo == "match_guia_tributo"]
    saida: list[GuiaResolvida] = []

    for r in alvo:
        valor = Decimal(str(abs(r.transacao.valor))).quantize(Decimal("0.01"))
        stmt = select(GuiaTributo).where(
            and_(
                GuiaTributo.cliente_id == cliente_id,
                GuiaTributo.ativo.is_(True),
                func.abs(GuiaTributo.valor - valor) <= TOLERANCIA_VALOR,
            )
        )
        linhas = (await db.execute(stmt)).scalars().all()

        if not linhas:
            saida.append(GuiaResolvida(
                r, "GUIA_NAO_ENCONTRADA",
                flag=f"sem guia de tributo no valor {valor:.2f} para o cliente",
            ))
            continue

        # Desempate por tipo (chave extraída na cascata: DARF, DAS, etc.)
        if len(linhas) > 1:
            mesmo_tipo = [g for g in linhas if g.tipo and g.tipo.upper() == r.chave.upper()]
            if len(mesmo_tipo) == 1:
                linhas = mesmo_tipo
            else:
                saida.append(GuiaResolvida(
                    r, "GUIA_AMBIGUA",
                    flag=(
                        f"{len(linhas)} guias no valor {valor:.2f} — "
                        "desempatar por competencia/vencimento"
                    ),
                ))
                continue

        g = linhas[0]
        saida.append(GuiaResolvida(
            r, "RESOLVIDO",
            tipo=g.tipo or "",
            competencia=g.competencia or "",
            conta_contabil=g.conta_contabil or "",
        ))

    return saida
