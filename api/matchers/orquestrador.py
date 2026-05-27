"""Orquestrador da cascata completa de 6 estágios — porta de `orgconc.py::conciliar`.

Despacha cada `Resultado` da classificação para o matcher do seu estágio,
combinando os resultados em uma lista de `Disposicao` (decisão final por
transação).

Estágios:
  0  transferência interna   → TRANSFERENCIA_INTERNA (fora da conciliação)
  1  CNPJ/CPF                → cadastro (clientes) → match_documento (base externa)
  2  número de NF            → match_nfe (XMLs)
  3  tarifa/juros            → TARIFA_BANCARIA (regra)
  4  tributo                 → match_guia
  5  contrato recorrente     → match_contrato
  6  resíduo                 → cadastro por alias; senão PENDENTE_FUZZY
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.matchers import contrapartes, contrato as m_contrato, documento, guia as m_guia, nfe as m_nfe
from api.matchers.cascata import Disposicao, Resultado


async def conciliar(
    resultados: list[Resultado],
    db: AsyncSession,
    cliente_id: uuid.UUID,
    xmls_nfe: Optional[list[tuple[str, bytes]]] = None,
) -> list[Disposicao]:
    """Despacha cada Resultado para o matcher do seu estágio."""
    xmls_nfe = xmls_nfe or []

    # ── Estágio 1: cadastro primeiro, base CNPJ como fallback ────────────
    stage1 = [r for r in resultados if r.estagio == 1]
    cadastro_hit: dict[int, contrapartes.CadastroContraparte] = {}
    base_misses: list[Resultado] = []
    for r in stage1:
        cp = await documento.consultar_por_documento(db, cliente_id, r.chave)
        if cp is not None:
            cadastro_hit[id(r)] = cp
        else:
            base_misses.append(r)
    base_results = await documento.resolver(base_misses, db)
    base_by_id = {id(dr.resultado): dr for dr in base_results}

    # ── Estágio 2: NFe ───────────────────────────────────────────────────
    nfe_results = await m_nfe.resolver(resultados, xmls_nfe) if xmls_nfe else []
    nfe_by_id = {id(nr.resultado): nr for nr in nfe_results}

    # ── Estágios 4 e 5: guia e contrato (DB) ─────────────────────────────
    guia_results = await m_guia.resolver(resultados, db, cliente_id)
    guia_by_id = {id(g.resultado): g for g in guia_results}

    contrato_results = await m_contrato.resolver(resultados, db, cliente_id)
    contrato_by_id = {id(c.resultado): c for c in contrato_results}

    # ── Despacho final ──────────────────────────────────────────────────
    disp: list[Disposicao] = []
    for r in resultados:
        t = r.transacao

        if r.estagio == 0:
            disp.append(Disposicao(
                t, 0, "TRANSFERENCIA_INTERNA", origem="regra",
                flag="nao e evento economico — excluir da conciliacao",
            ))

        elif r.estagio == 1:
            cp = cadastro_hit.get(id(r))
            if cp is not None:
                disp.append(Disposicao(
                    t, 1, "RESOLVIDO_CADASTRO",
                    contraparte=cp.nome_real, conta_contabil=cp.conta_contabil,
                    origem="cadastro",
                ))
            else:
                cr = base_by_id.get(id(r))
                if cr and cr.status == "RESOLVIDO_BASE":
                    disp.append(Disposicao(
                        t, 1, "RESOLVIDO_BASE",
                        contraparte=cr.razao_social, origem="base_cnpj",
                        flag=cr.flag or "nova contraparte — sugerir cadastro",
                    ))
                else:
                    disp.append(Disposicao(
                        t, 1, (cr.status if cr else "NAO_ENCONTRADO"),
                        origem="base_cnpj", flag=cr.flag if cr else "",
                    ))

        elif r.estagio == 2:
            nr = nfe_by_id.get(id(r))
            if nr is None:
                disp.append(Disposicao(
                    t, 2, "PENDENTE_MATCHER", origem="match_nfe",
                    flag="nenhum XML de NF-e foi enviado junto",
                ))
            elif nr.status == "RESOLVIDO":
                nf = nr.nota
                disp.append(Disposicao(
                    t, 2, "RESOLVIDO_NFE",
                    contraparte=(nf.emit_nome or nf.emit_cnpj) if nf else "",
                    origem="nfe", flag=nr.flag,
                    nfe_chave=nf.chave if nf else "",
                ))
            else:
                disp.append(Disposicao(
                    t, 2, "PENDENTE_REVISAO", origem="match_nfe", flag=nr.flag,
                ))

        elif r.estagio == 3:
            disp.append(Disposicao(
                t, 3, "TARIFA_BANCARIA",
                contraparte="Despesa bancaria", origem="regra",
            ))

        elif r.estagio == 4:
            g = guia_by_id.get(id(r))
            if g and g.status == "RESOLVIDO":
                disp.append(Disposicao(
                    t, 4, "RESOLVIDO_GUIA",
                    contraparte=f"Tributo {g.tipo}",
                    conta_contabil=g.conta_contabil, origem="guia",
                ))
            else:
                disp.append(Disposicao(
                    t, 4, "PENDENTE_REVISAO", origem="match_guia",
                    flag=g.flag if g else "",
                ))

        elif r.estagio == 5:
            c = contrato_by_id.get(id(r))
            if c and c.status == "RESOLVIDO":
                disp.append(Disposicao(
                    t, 5, "RESOLVIDO_CONTRATO",
                    contraparte=c.descricao,
                    conta_contabil=c.conta_contabil, origem="contrato",
                ))
            else:
                disp.append(Disposicao(
                    t, 5, "PENDENTE_REVISAO", origem="match_contrato",
                    flag=c.flag if c else "",
                ))

        elif r.estagio == 6:
            cp = await contrapartes.consultar_por_alias(db, cliente_id, t.nome or t.memo)
            if cp is not None:
                disp.append(Disposicao(
                    t, 6, "RESOLVIDO_CADASTRO",
                    contraparte=cp.nome_real, conta_contabil=cp.conta_contabil,
                    origem="cadastro(alias)",
                ))
            else:
                disp.append(Disposicao(
                    t, 6, "PENDENTE_FUZZY", origem="fuzzy_llm",
                    flag="sem alias no cadastro — vai para o matcher fuzzy/LLM",
                ))

    return disp


_AUTOMATICO = {
    "RESOLVIDO_CADASTRO", "RESOLVIDO_BASE", "RESOLVIDO_NFE",
    "RESOLVIDO_GUIA", "RESOLVIDO_CONTRATO", "TARIFA_BANCARIA",
    "TRANSFERENCIA_INTERNA",
}


def taxa_automatizacao(disposicoes: list[Disposicao]) -> float:
    """Retorna o % de transações com disposição automática (sem revisão humana)."""
    total = len(disposicoes)
    if not total:
        return 0.0
    auto = sum(1 for d in disposicoes if d.disposicao in _AUTOMATICO)
    return round(100 * auto / total, 1)
