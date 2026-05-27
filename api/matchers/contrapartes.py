"""Consulta de contrapartes por alias (estágio 6 da cascata).

Substitui `cadastro_contrapartes.py` do OrgNeural2. Usa a tabela `clientes`
existente; aliases (texto curto presente no memo/nome bancário, ex: "FAV.:
RENATO COSTA SERVIÇOS") são procurados via ILIKE no campo `nome`.

Backlog: tabela dedicada `cliente_alias(cliente_id, alias)` para mapeamentos
explícitos definidos pelo contador.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Cliente


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


async def consultar_por_alias(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    alias: str,
) -> CadastroContraparte | None:
    """Busca cliente cujo nome contenha o alias informado (case-insensitive)."""
    alvo = _normaliza_alias(alias)
    if len(alvo) < 4:
        return None
    stmt = select(Cliente).where(Cliente.nome.ilike(f"%{alvo}%")).limit(2)
    candidatos = (await db.execute(stmt)).scalars().all()
    if len(candidatos) == 1:
        c = candidatos[0]
        return CadastroContraparte(nome_real=c.nome, conta_contabil="")
    return None
