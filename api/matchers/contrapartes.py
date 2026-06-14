"""Consulta de contrapartes por alias (estágio 6 da cascata).

Substitui `cadastro_contrapartes.py` do OrgNeural2. Usa a tabela `clientes`
existente; aliases (texto curto presente no memo/nome bancário, ex: "FAV.:
FULANO DE TAL SERVIÇOS") são procurados via ILIKE no campo `nome`.

Backlog: tabela dedicada `cliente_alias(cliente_id, alias)` para mapeamentos
explícitos definidos pelo contador.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Cliente
from api.db.rls_context import get_org_context
from api.matchers.documento import _coerce_org


@dataclass
class CadastroContraparte:
    nome_real: str
    conta_contabil: str = ""


def _normaliza_alias(s: str) -> str:
    """Limpa prefixos típicos do memo bancário (ex: 'FAV.:', 'PAGAMENTO')."""
    if not s:
        return ""
    texto = s.strip()
    for prefixo in ("FAV.:", "FAV:", "FAV.", "FAVORECIDO:", "PAGAMENTO"):
        if texto.upper().startswith(prefixo):
            texto = texto[len(prefixo):].strip(" :")
    return texto


def _escapa_like(s: str) -> str:
    r"""Escapa os curingas do LIKE/ILIKE (`%`, `_`) e o próprio escape (`\`).

    Sem isso, um alias como 'FULANO_DE_TAL' ou 'EMPRESA 100%' seria interpretado
    como padrão (o `_` casa 1 char qualquer; o `%` casa qualquer sequência),
    causando matching incorreto. Usado com `ilike(..., escape='\\')`.
    """
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def consultar_por_alias(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    alias: str,
    org_id: str | uuid.UUID | None = None,
) -> CadastroContraparte | None:
    """Busca cliente cujo nome contenha o alias informado (case-insensitive).

    Restrito ao tenant: a coluna de tenant da tabela `clientes` é `org_id`
    (o `cliente_id` é o id do cliente da firma contábil, mantido por compat com
    o orquestrador). Defesa em profundidade — a RLS já filtra por `org_id` no
    banco; este `.where` explícito reforça o isolamento na query. O `org_id` vem
    do parâmetro (testes) ou do contexto de RLS (`get_org_context`); sem tenant
    no contexto a consulta é global (comportamento legado preservado).

    Os curingas de LIKE no alias são escapados para evitar matching indevido.
    """
    alvo = _normaliza_alias(alias)
    if len(alvo) < 4:
        return None
    padrao = f"%{_escapa_like(alvo)}%"
    org = _coerce_org(org_id if org_id is not None else get_org_context())
    stmt = select(Cliente).where(Cliente.nome.ilike(padrao, escape="\\"))
    if org is not None:
        stmt = stmt.where(Cliente.org_id == org)
    stmt = stmt.limit(2)
    candidatos = (await db.execute(stmt)).scalars().all()
    if len(candidatos) == 1:
        c = candidatos[0]
        return CadastroContraparte(nome_real=c.nome, conta_contabil="")
    return None
