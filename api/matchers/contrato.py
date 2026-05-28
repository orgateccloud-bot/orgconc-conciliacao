"""Matcher do estágio 5 — casa transações contra contratos recorrentes cadastrados.

Porta de `D:\\00_Inbox\\OrgNeural2\\match_contrato.py` para SQLAlchemy async.
Critério: mesmo cliente + valor coincidente (±R$0.01). Desempata pelo trecho
`padrao_memo` esperado no MEMO da transação.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Contrato
from api.matchers.cascata import Resultado

TOLERANCIA_VALOR = Decimal("0.01")


@dataclass
class ContratoResolvido:
    resultado: Resultado
    status: str           # RESOLVIDO / CONTRATO_NAO_ENCONTRADO / CONTRATO_AMBIGUO
    descricao: str = ""
    conta_contabil: str = ""
    flag: str = ""


async def resolver(
    resultados: list[Resultado],
    db: AsyncSession,
    cliente_id: uuid.UUID,
) -> list[ContratoResolvido]:
    """Casa transações do estágio 5 (match_contrato) contra cadastro."""
    alvo = [r for r in resultados if r.metodo == "match_contrato"]
    saida: list[ContratoResolvido] = []

    for r in alvo:
        valor = Decimal(str(abs(r.transacao.valor))).quantize(Decimal("0.01"))
        stmt = select(Contrato).where(
            and_(
                Contrato.cliente_id == cliente_id,
                Contrato.ativo.is_(True),
                func.abs(Contrato.valor - valor) <= TOLERANCIA_VALOR,
            )
        )
        linhas = (await db.execute(stmt)).scalars().all()

        if not linhas:
            saida.append(ContratoResolvido(
                r, "CONTRATO_NAO_ENCONTRADO",
                flag=f"sem contrato no valor {valor:.2f} para o cliente",
            ))
            continue

        # Desempate pelo padrão esperado no MEMO da transação
        if len(linhas) > 1:
            memo = (r.transacao.memo or "").upper()
            casados = [c for c in linhas if c.padrao_memo and c.padrao_memo.upper() in memo]
            if len(casados) == 1:
                linhas = casados
            else:
                saida.append(ContratoResolvido(
                    r, "CONTRATO_AMBIGUO",
                    flag=(
                        f"{len(linhas)} contratos no valor {valor:.2f} — "
                        "desempatar por descricao/periodicidade"
                    ),
                ))
                continue

        c = linhas[0]
        saida.append(ContratoResolvido(
            r, "RESOLVIDO",
            descricao=c.descricao or "",
            conta_contabil=c.conta_contabil or "",
        ))

    return saida
