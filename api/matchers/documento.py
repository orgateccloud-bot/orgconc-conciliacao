"""Matcher do estágio 1 — resolve via cadastro de clientes (CNPJ/CPF explícito).

Versão MVP: consulta a tabela `clientes` pelo CNPJ. Sem base externa (Receita
Federal) por ora — fica como backlog. Retorna `RESOLVIDO_CADASTRO` quando achar
um cliente ativo com o CNPJ, ou `NAO_ENCONTRADO`.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Cliente
from api.matchers.cascata import Resultado


@dataclass
class DocumentoResolvido:
    resultado: Resultado
    status: str           # RESOLVIDO_BASE / NAO_ENCONTRADO / DOC_INVALIDO
    razao_social: str = ""
    cnpj_normalizado: str = ""
    flag: str = ""


def _normaliza_cnpj(s: str) -> str:
    return re.sub(r"\D", "", s or "")


async def resolver(
    resultados: list[Resultado],
    db: AsyncSession,
) -> list[DocumentoResolvido]:
    """Resolve transações do estágio 1 (CNPJ explícito) contra a tabela clientes."""
    alvo = [r for r in resultados if r.metodo == "match_documento"]
    saida: list[DocumentoResolvido] = []

    for r in alvo:
        digitos = _normaliza_cnpj(r.chave)
        if len(digitos) != 14:
            saida.append(DocumentoResolvido(
                r, "DOC_INVALIDO",
                flag=f"documento {r.chave} não tem 14 dígitos",
            ))
            continue

        # Formato canônico armazenado em clientes.cnpj é XX.XXX.XXX/XXXX-XX
        formatado = (
            f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/"
            f"{digitos[8:12]}-{digitos[12:14]}"
        )
        stmt = select(Cliente).where(
            (Cliente.cnpj == formatado) | (Cliente.cnpj == digitos)
        )
        cliente = (await db.execute(stmt)).scalar_one_or_none()

        if cliente is None:
            saida.append(DocumentoResolvido(
                r, "NAO_ENCONTRADO",
                cnpj_normalizado=digitos,
                flag="CNPJ não cadastrado — sugerir novo cliente",
            ))
            continue

        saida.append(DocumentoResolvido(
            r, "RESOLVIDO_BASE",
            razao_social=cliente.nome,
            cnpj_normalizado=digitos,
            flag="" if cliente.ativo else "ALERTA: cliente marcado como inativo",
        ))

    return saida


# ────────────────────────────────────────────────────────────────────────
# Consulta direta usada pelo orquestrador (cascata.py do OrgNeural2 →
# cadastro_contrapartes.consultar_por_documento). Para o MVP, consulta a
# própria tabela clientes pelo CNPJ.
# ────────────────────────────────────────────────────────────────────────


@dataclass
class CadastroContraparte:
    nome_real: str
    conta_contabil: str = ""


async def consultar_por_documento(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    doc: str,
) -> CadastroContraparte | None:
    """Consulta cadastro por CNPJ. cliente_id é o tenant da firma contábil.

    MVP: consulta global da tabela clientes (não multi-tenant ainda — o
    cliente_id é aceito por compatibilidade com o orquestrador).
    """
    digitos = _normaliza_cnpj(doc)
    if len(digitos) != 14:
        return None
    formatado = (
        f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/"
        f"{digitos[8:12]}-{digitos[12:14]}"
    )
    stmt = select(Cliente).where(
        (Cliente.cnpj == formatado) | (Cliente.cnpj == digitos)
    )
    cliente = (await db.execute(stmt)).scalar_one_or_none()
    if cliente is None:
        return None
    return CadastroContraparte(nome_real=cliente.nome, conta_contabil="")
