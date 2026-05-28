"""Matcher do estágio 2 — casa transações contra XMLs de NF-e.

Porta de `D:\\00_Inbox\\OrgNeural2\\match_nfe.py` adaptada para o OrgConc:
- `indexar()` recebe lista de `(filename, bytes)` em vez de path no disco.
- `resolver()` é `async def` para integração com FastAPI.
- Mantém o algoritmo de matching original: número da NF (sem zeros à esquerda)
  + desempate por valor (tolerância R$0.01).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

from api.matchers.cascata import Resultado

TOLERANCIA_VALOR = 0.01   # diferença aceita como "mesmo valor" (R$)


@dataclass
class NotaFiscal:
    numero: str
    serie: str
    chave: str           # chave de acesso (44 dígitos)
    data_emissao: str    # AAAA-MM-DD
    emit_cnpj: str
    emit_nome: str
    dest_doc: str
    dest_nome: str
    valor: float


@dataclass
class NotaResolvida:
    resultado: Resultado
    status: str          # RESOLVIDO / NF_NAO_ENCONTRADA / NF_AMBIGUA
    nota: Optional[NotaFiscal] = None
    flag: str = ""


# ────────────────────────────────────────────────────────────────────────
# Parser de NF-e — agnóstico a namespace
# ────────────────────────────────────────────────────────────────────────


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _filho(elem, nome: str):
    if elem is None:
        return None
    for f in elem:
        if _local(f.tag) == nome:
            return f
    return None


def _texto(elem, *caminho: str) -> str:
    cur = elem
    for nome in caminho:
        cur = _filho(cur, nome)
        if cur is None:
            return ""
    return cur.text.strip() if cur is not None and cur.text else ""


def _achar_infnfe(root):
    for elem in root.iter():
        if _local(elem.tag) == "infNFe":
            return elem
    return None


def ler_nfe_bytes(conteudo: bytes) -> Optional[NotaFiscal]:
    """Lê um XML de NF-e (bytes) e devolve a NotaFiscal, ou None se não for NF-e."""
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError:
        return None
    inf = _achar_infnfe(root)
    if inf is None:
        return None

    ide = _filho(inf, "ide")
    emit = _filho(inf, "emit")
    dest = _filho(inf, "dest")

    chave = (inf.get("Id") or "").lstrip("NFe")
    data = (_texto(ide, "dhEmi") or _texto(ide, "dEmi"))[:10]

    dest_doc = ""
    if dest is not None:
        dest_doc = _texto(dest, "CNPJ") or _texto(dest, "CPF")

    total = _filho(inf, "total")
    valor_txt = ""
    if total is not None:
        valor_txt = _texto(total, "ICMSTot", "vNF") or _texto(total, "vNF")

    return NotaFiscal(
        numero=_texto(ide, "nNF"),
        serie=_texto(ide, "serie"),
        chave=chave,
        data_emissao=data,
        emit_cnpj=_texto(emit, "CNPJ"),
        emit_nome=_texto(emit, "xNome"),
        dest_doc=dest_doc,
        dest_nome=_texto(dest, "xNome") if dest is not None else "",
        valor=float(valor_txt) if valor_txt else 0.0,
    )


def indexar_bytes(xmls: list[tuple[str, bytes]]) -> dict[str, list[NotaFiscal]]:
    """Indexa uma lista de (nome_arquivo, conteúdo_bytes) de XMLs por número de NF."""
    indice: dict[str, list[NotaFiscal]] = {}
    for _filename, conteudo in xmls:
        nf = ler_nfe_bytes(conteudo)
        if nf is None or not nf.numero:
            continue
        try:
            chave = str(int(nf.numero))     # normaliza zeros à esquerda
        except ValueError:
            continue
        indice.setdefault(chave, []).append(nf)
    return indice


# ────────────────────────────────────────────────────────────────────────
# Matcher
# ────────────────────────────────────────────────────────────────────────


async def resolver(
    resultados: list[Resultado],
    xmls: list[tuple[str, bytes]],
) -> list[NotaResolvida]:
    """Casa transações do estágio 2 contra os XMLs de NF-e fornecidos."""
    indice = indexar_bytes(xmls)
    alvo = [r for r in resultados if r.metodo == "match_nfe"]

    saida: list[NotaResolvida] = []
    for r in alvo:
        try:
            chave = str(int(r.chave))
        except (ValueError, TypeError):
            saida.append(NotaResolvida(
                r, "NF_NAO_ENCONTRADA",
                flag="numero de NF nao numerico",
            ))
            continue

        candidatos = indice.get(chave, [])
        if not candidatos:
            saida.append(NotaResolvida(
                r, "NF_NAO_ENCONTRADA",
                flag=f"NF {chave} ausente na pasta de XMLs",
            ))
            continue

        valor_trn = abs(r.transacao.valor)
        por_valor = [
            nf for nf in candidatos
            if abs(nf.valor - valor_trn) <= TOLERANCIA_VALOR
        ]

        if len(por_valor) == 1:
            saida.append(NotaResolvida(r, "RESOLVIDO", nota=por_valor[0]))
        elif len(por_valor) > 1:
            saida.append(NotaResolvida(
                r, "NF_AMBIGUA",
                flag=(
                    f"{len(por_valor)} NFs com nº {chave} e mesmo valor "
                    "— desempatar por data/emitente"
                ),
            ))
        elif len(candidatos) == 1:
            saida.append(NotaResolvida(
                r, "RESOLVIDO", nota=candidatos[0],
                flag="valor do lancamento diverge do valor da NF — revisar",
            ))
        else:
            saida.append(NotaResolvida(
                r, "NF_AMBIGUA",
                flag=(
                    f"{len(candidatos)} NFs com nº {chave}, "
                    "nenhuma com valor coincidente"
                ),
            ))
    return saida
