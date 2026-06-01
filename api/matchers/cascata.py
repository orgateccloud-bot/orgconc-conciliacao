"""Cascata de classificação — substitui o módulo externo `cascata.py` do OrgNeural2.

Reusa `api/parsers/ofx._parse_ofx` para ler OFX e `api/parsers/classifier._classificar`
para classificação contábil. Expõe:

- `Transacao`  : forma compacta de uma linha de extrato (compatível com matchers).
- `Resultado`  : transação classificada com `metodo` para roteamento na cascata.
- `Disposicao` : decisão final pós-matchers (saída do orquestrador).
- `ler_ofx()`  : adapter que retorna `list[Transacao]` lendo OFX.
- `classificar(t)` : roteia cada Transacao para um dos métodos da cascata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from api.parsers.constants import GUIA_TRIBUTO_TIPOS
from api.parsers.ofx import _parse_ofx


# ────────────────────────────────────────────────────────────────────────
# Modelos
# ────────────────────────────────────────────────────────────────────────


@dataclass
class Transacao:
    """Linha de extrato — formato compacto comum aos matchers."""
    data: str           # AAAA-MM-DD
    tipo: str           # DEBIT / CREDIT
    valor: float        # negativo para débito
    fitid: str          # ID único no extrato
    memo: str           # descrição do banco
    nome: str           # contraparte/favorecido
    conta: str = ""     # identificação da conta de origem
    checknum: str = ""  # número do cheque/documento (CHECKNUM do OFX)


@dataclass
class Resultado:
    """Transação classificada com sugestão de método de matching."""
    transacao: Transacao
    estagio: int        # 0..6
    metodo: str         # transferencia_interna | match_documento | match_nfe |
                        # tarifa_bancaria | match_guia_tributo | match_contrato |
                        # match_cadastro_alias
    chave: str = ""     # número de NF, CNPJ, tipo de tributo, etc.
    contraparte: str = ""


@dataclass
class Disposicao:
    """Disposição final após toda a cascata — saída do orquestrador."""
    transacao: Transacao
    estagio: int
    disposicao: str        # RESOLVIDO_NFE, PENDENTE_REVISAO, etc.
    contraparte: str = ""
    conta_contabil: str = ""
    origem: str = ""       # nfe / guia / contrato / cadastro / regra / fuzzy_llm
    flag: str = ""
    nfe_chave: str = ""    # chave de acesso da NF-e (44 dígitos) quando matched


# ────────────────────────────────────────────────────────────────────────
# Adapter: OFX → list[Transacao]
# ────────────────────────────────────────────────────────────────────────


def ler_ofx(path_or_bytes) -> list[Transacao]:
    """Lê OFX (path ou bytes) e devolve list[Transacao].

    Reusa o parser `api.parsers.ofx._parse_ofx` que já trata SGML.
    """
    if isinstance(path_or_bytes, (str, bytes, bytearray)):
        if isinstance(path_or_bytes, str):
            with open(path_or_bytes, "rb") as fh:
                conteudo = fh.read()
        else:
            conteudo = bytes(path_or_bytes)
    else:  # file-like
        conteudo = path_or_bytes.read()

    try:
        texto = conteudo.decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        texto = conteudo.decode("latin-1", errors="ignore")

    transacoes_dict = _parse_ofx(texto)
    saida: list[Transacao] = []
    for t in transacoes_dict:
        valor = float(t.get("valor", 0))
        tipo = (t.get("tipo") or "").upper()
        if not tipo:
            tipo = "DEBIT" if valor < 0 else "CREDIT"
        saida.append(Transacao(
            data=str(t.get("data") or "")[:10],
            tipo=tipo,
            valor=valor,
            fitid=str(t.get("fitid") or ""),
            memo=str(t.get("memo") or ""),
            nome=str(t.get("nome") or ""),
            conta=str(t.get("conta") or ""),
            checknum=str(t.get("checknum") or ""),
        ))
    return saida


# ────────────────────────────────────────────────────────────────────────
# Classificador — roteia para método do matcher
# ────────────────────────────────────────────────────────────────────────


_RX_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_RX_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_RX_NF = re.compile(r"\bnf[\s:]*([0-9]{1,9})\b", re.IGNORECASE)

_TRIBUTOS = GUIA_TRIBUTO_TIPOS  # fonte unica em api/parsers/constants
_TARIFAS = ("TARIFA", "JUROS", "IOF", "TAR.", "TARIF")

# Palavras-chave que indicam transferência INTERNA real (mesma titularidade).
# Mais restritivo que parsers.constants._KEYWORDS_TRANSF (que pega qualquer
# TRANSF.CONTAS, incluindo "DIFERENTE" que é transferência a terceiro).
_KEYWORDS_TRANSF_INTERNA = (
    "MESMA TIT",
    "MESMA TITULARIDADE",
    "TRANSF MESMA",
    "TRANSFERENCIA ENTRE CONTAS PROPRIAS",
    "ENTRE CONTAS PROPRIAS",
    "PROPRIO CLIENTE",
)


def _detecta_transferencia(memo: str, nome: str) -> bool:
    texto = (memo + " " + nome).upper()
    return any(k in texto for k in _KEYWORDS_TRANSF_INTERNA)


def _detecta_tarifa(memo: str, nome: str) -> bool:
    texto = (memo + " " + nome).upper()
    return any(k in texto for k in _TARIFAS)


def _detecta_tributo(memo: str, nome: str) -> Optional[str]:
    texto = (memo + " " + nome).upper()
    for t in _TRIBUTOS:
        if t in texto:
            return t
    return None


def _extrai_numero_nf(memo: str, nome: str) -> Optional[str]:
    for fonte in (nome, memo):
        m = _RX_NF.search(fonte or "")
        if m:
            return m.group(1)
    return None


def _extrai_cnpj_cpf(memo: str, nome: str) -> Optional[str]:
    for fonte in (nome, memo):
        m = _RX_CNPJ.search(fonte or "") or _RX_CPF.search(fonte or "")
        if m:
            return re.sub(r"\D", "", m.group(0))
    return None


def classificar(t: Transacao) -> Resultado:
    """Roteia uma transação para o método do matcher correto."""
    memo = t.memo or ""
    nome = t.nome or ""

    # Estágio 0 — transferência entre contas próprias
    if _detecta_transferencia(memo, nome):
        return Resultado(t, estagio=0, metodo="transferencia_interna")

    # Estágio 3 — tarifa bancária (antes de tudo que precisa de matching pesado)
    if _detecta_tarifa(memo, nome):
        return Resultado(t, estagio=3, metodo="tarifa_bancaria")

    # Estágio 4 — tributo (DARF, DAS, etc.)
    tributo = _detecta_tributo(memo, nome)
    if tributo:
        return Resultado(t, estagio=4, metodo="match_guia_tributo", chave=tributo)

    # Estágio 2 — número de NF no memo/nome
    n_nf = _extrai_numero_nf(memo, nome)
    if n_nf:
        return Resultado(t, estagio=2, metodo="match_nfe", chave=n_nf)

    # Estágio 1 — CNPJ/CPF explícito → match contra cadastro
    doc = _extrai_cnpj_cpf(memo, nome)
    if doc:
        return Resultado(t, estagio=1, metodo="match_documento", chave=doc)

    # Estágio 6 — débito a favorecido por nome (FAV.:, PAGAMENTO A, etc.)
    # — vai direto para alias (não tenta contrato; estes débitos não são fixos)
    texto = (memo + " " + nome).upper()
    if "FAV.:" in texto or "FAV:" in texto or "FAVORECIDO" in texto:
        return Resultado(t, estagio=6, metodo="match_cadastro_alias")

    # Estágio 5 — débito recorrente sem identificador → tenta contrato
    # (típico: DEB.CONV.SEGUROS, DEB.AUTOMATICO ALUGUEL — sem favorecido nominal)
    if t.tipo.upper() == "DEBIT":
        return Resultado(t, estagio=5, metodo="match_contrato")

    # Estágio 6 — fallback final: alias/fuzzy
    return Resultado(t, estagio=6, metodo="match_cadastro_alias")
