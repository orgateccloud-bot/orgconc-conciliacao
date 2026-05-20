"""Parsers de extratos bancarios + classificador contabil + detector de anomalias.

Funcoes publicas (mantem prefixo _ por compat com api.main):
- _parse_arquivo(content, filename) -> list[dict]    | router por extensao
- _parse_ofx(text) -> list[dict]                      | parser OFX SGML
- _parse_xml(text, filename) -> list[dict]            | parser CAMT.053 ou OFX-XML
- _parse_pdf(content, filename) -> list[dict]         | parser PDF bancario
- _classificar(memo, nome) -> str                     | classificador contabil
- _detectar_anomalias(extratos) -> list[dict]         | detector multi-severidade
- _top_categorias_e_contrapartes(extratos) -> dict    | estatisticas
- _fmt_csv(transacoes) -> str                         | formata CSV para prompt LLM
"""
from __future__ import annotations

import io
import logging
import re
import defusedxml.ElementTree as ET  # substitui stdlib ET — previne XXE e XML bomb
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Optional

import pdfplumber
from fastapi import HTTPException

log = logging.getLogger("orgconc.parsers")


# ── OFX ─────────────────────────────────────────────────────────────────────

def _parse_ofx(text: str) -> list[dict]:
    """Parser OFX minimalista (SGML)."""
    branch_m = re.search(r"<BRANCHID>([^<\n]+)", text)
    acct_m = re.search(r"<ACCTID>([^<\n]+)", text)
    conta = f"AG {branch_m.group(1).strip() if branch_m else '?'} / CC {acct_m.group(1).strip() if acct_m else '?'}"
    transacoes: list[dict] = []
    for bloco in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, flags=re.DOTALL):
        def fld(tag: str) -> str:
            m = re.search(rf"<{tag}>([^<\n]*)", bloco)
            return m.group(1).strip() if m else ""

        data_raw = fld("DTPOSTED")[:8]
        data = (
            f"{data_raw[:4]}-{data_raw[4:6]}-{data_raw[6:8]}"
            if len(data_raw) == 8 else data_raw
        )
        transacoes.append({
            "conta": conta,
            "data": data,
            "tipo": fld("TRNTYPE"),
            "valor": float(fld("TRNAMT") or 0),
            "memo": fld("MEMO"),
            "nome": fld("NAME"),
            "checknum": fld("CHECKNUM"),
        })
    return transacoes


# ── XML (CAMT.053 ou OFX-XML) ────────────────────────────────────────────────

def _parse_xml(text: str, filename: str) -> list[dict]:
    """Extrai transacoes de XML (CAMT.053, padrao bancario brasileiro, ou OFX em XML)."""
    transacoes: list[dict] = []
    conta_default = f"XML ({filename})"
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    def _strip_ns(el):
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
        for child in el:
            _strip_ns(child)
    _strip_ns(root)

    conta = conta_default
    acct = None
    for xpath in (".//Acct/Id/Othr/Id", ".//Acct/Id", ".//ACCTID", ".//Id"):
        acct = root.find(xpath)
        if acct is not None:
            break
    if acct is not None and acct.text:
        conta = f"Conta {acct.text.strip()}"

    for ntry in root.iter("Ntry"):
        amt = ntry.find("Amt")
        cdtdbt = ntry.find("CdtDbtInd")
        dt_el = ntry.find("BookgDt/Dt")
        if dt_el is None:
            dt_el = ntry.find("ValDt/Dt")
        dt = dt_el
        info = ntry.find(".//AddtlNtryInf")
        if info is None:
            info = ntry.find(".//RmtInf/Ustrd")
        if amt is None or cdtdbt is None or dt is None:
            continue
        try:
            valor = float(amt.text)
        except (TypeError, ValueError):
            continue
        if cdtdbt.text == "DBIT":
            valor = -abs(valor)
        transacoes.append({
            "conta": conta,
            "data": dt.text[:10],
            "tipo": "CREDIT" if valor > 0 else "DEBIT",
            "valor": valor,
            "memo": (info.text.strip() if info is not None and info.text else ""),
            "nome": "",
            "checknum": "",
        })

    if not transacoes:
        for tr in root.iter("STMTTRN"):
            data = (tr.findtext("DTPOSTED") or "")[:8]
            data_iso = f"{data[:4]}-{data[4:6]}-{data[6:8]}" if len(data) == 8 else data
            try:
                valor = float(tr.findtext("TRNAMT") or 0)
            except ValueError:
                continue
            transacoes.append({
                "conta": conta,
                "data": data_iso,
                "tipo": tr.findtext("TRNTYPE") or "",
                "valor": valor,
                "memo": (tr.findtext("MEMO") or "").strip(),
                "nome": (tr.findtext("NAME") or "").strip(),
                "checknum": (tr.findtext("CHECKNUM") or "").strip(),
            })

    return transacoes


# ── PDF ──────────────────────────────────────────────────────────────────────

def _parse_pdf(content: bytes, filename: str) -> list[dict]:
    """Extrai transacoes de PDF de extrato bancario com 3 estrategias em fallback."""
    transacoes: list[dict] = []
    conta_default = f"PDF ({filename})"

    conta_detectada: Optional[str] = None
    rx_conta = re.compile(
        r"(?:AG[EÊE]?N?CIA|AG[ÊE]?)\s*:?\s*(\d{3,5}[-\d]?)\s+"
        r"(?:CONTA|C\.?C\.?|CC)\s*:?\s*(\d{4,10}[-\d]?)",
        re.IGNORECASE,
    )
    rx_sinal_dc = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+(.{5,80}?)\s+([\d.]+,\d{2})\s*([CD])\b",
        re.IGNORECASE,
    )
    rx_padrao = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+(.{5,80}?)\s+([+\-]?\s*R?\$?\s*[\d.]+,\d{2})"
    )
    rx_compacta = re.compile(
        r"(\d{2}/\d{2}/\d{2,4})\s+(.{3,80}?)\s+(\(?\s*[+\-]?\s*[\d.]+,\d{2}\s*\)?)"
    )

    keywords_debito = ("PAGTO", "DEBITO", "DÉBITO", "DEB ", "PIX EMITIDO", "PIX ENVIADO",
                       "SAQUE", "COMPRA", "TARIFA", "JUROS", "IOF", "BOLETO", "TED ENVIADA",
                       "DOC ENVIADO", "PAGAMENTO", "ESTORNO DEB", "RETIRADA")

    def parse_valor(s: str) -> Optional[float]:
        s = s.strip()
        neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
        s = s.strip("()").replace("R", "").replace("$", "").replace(" ", "")
        s = s.replace(".", "").replace(",", ".").lstrip("+-")
        try:
            v = float(s)
            return -v if neg else v
        except ValueError:
            return None

    def parse_data(s: str) -> Optional[str]:
        partes = s.split("/")
        if len(partes) != 3:
            return None
        dia, mes, ano = partes
        if len(ano) == 2:
            ano = "20" + ano
        if len(dia) != 2 or len(mes) != 2 or len(ano) != 4:
            return None
        return f"{ano}-{mes}-{dia}"

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if conta_detectada is None:
                    m_conta = rx_conta.search(text)
                    if m_conta:
                        ag, cc = m_conta.groups()
                        conta_detectada = f"AG {ag} / CC {cc}"

                vistos = set()

                for m in rx_sinal_dc.finditer(text):
                    data_br, desc, valor_s, sinal = m.groups()
                    data_iso = parse_data(data_br)
                    valor = parse_valor(valor_s)
                    if not data_iso or valor is None:
                        continue
                    valor = -abs(valor) if sinal.upper() == "D" else abs(valor)
                    chave = (data_iso, round(valor, 2), desc.strip()[:40])
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    transacoes.append({
                        "conta": conta_detectada or conta_default,
                        "data": data_iso, "tipo": "CREDIT" if valor > 0 else "DEBIT",
                        "valor": valor, "memo": desc.strip(),
                        "nome": "", "checknum": "",
                    })

                for m in rx_padrao.finditer(text):
                    data_br, desc, valor_s = m.groups()
                    data_iso = parse_data(data_br)
                    valor = parse_valor(valor_s)
                    if not data_iso or valor is None:
                        continue
                    desc_up = desc.upper()
                    if "+" not in valor_s and "-" not in valor_s and "(" not in valor_s:
                        if any(k in desc_up for k in keywords_debito):
                            valor = -abs(valor)
                    chave = (data_iso, round(valor, 2), desc.strip()[:40])
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    transacoes.append({
                        "conta": conta_detectada or conta_default,
                        "data": data_iso, "tipo": "CREDIT" if valor > 0 else "DEBIT",
                        "valor": valor, "memo": desc.strip(),
                        "nome": "", "checknum": "",
                    })

                if not transacoes:
                    for m in rx_compacta.finditer(text):
                        data_br, desc, valor_s = m.groups()
                        data_iso = parse_data(data_br)
                        valor = parse_valor(valor_s)
                        if not data_iso or valor is None:
                            continue
                        chave = (data_iso, round(valor, 2), desc.strip()[:40])
                        if chave in vistos:
                            continue
                        vistos.add(chave)
                        transacoes.append({
                            "conta": conta_detectada or conta_default,
                            "data": data_iso, "tipo": "CREDIT" if valor > 0 else "DEBIT",
                            "valor": valor, "memo": desc.strip(),
                            "nome": "", "checknum": "",
                        })
    except Exception as e:
        log.exception("Erro parseando PDF %s", filename)
        raise HTTPException(status_code=400, detail=f"PDF invalido ou corrompido: {e}")

    log.info("PDF %s: %d transacoes extraidas", filename, len(transacoes))
    return transacoes


# ── Router por extensao ──────────────────────────────────────────────────────

def _parse_arquivo(content: bytes, filename: str) -> list[dict]:
    """Detecta tipo do arquivo e roteia para o parser correto."""
    ext = Path(filename).suffix.lower()
    if ext == ".ofx":
        return _parse_ofx(content.decode("latin-1", errors="ignore"))
    if ext == ".pdf":
        return _parse_pdf(content, filename)
    if ext == ".xml":
        return _parse_xml(content.decode("utf-8", errors="ignore"), filename)
    raise HTTPException(
        status_code=400,
        detail=f"Extensao nao suportada: {ext}. Use .ofx, .pdf ou .xml",
    )


# ── Classificador contabil ───────────────────────────────────────────────────

_REGRAS_ANTES_PIX: list[tuple[tuple[str, ...], str]] = [
    (("INTERCREDIS", "TRANSF.CONTAS", "TRANSF. CONTAS", "TRANSF MESMA TIT",
      "TRANSFERENCIA MESMA TITULARIDADE", "TRANSFERENCIA ENTRE CONTAS PROPRIAS"),
     "Transferencia entre contas proprias"),
    (("DAS ", "DARF", "RFB", "INSS", "FGTS", "DAE", "GPS", "GNRE", "DAR ",
      "IRRF", "IRPJ", "CSLL", "ICMS", "ISS", "GUIA"),
     "Tributo"),
    (("IOF",), "Despesa Financeira - IOF"),
    (("JUROS", "MORA"), "Despesa Financeira - Juros"),
    (("MULTA",), "Despesa Financeira - Multa"),
    (("PAGAMENTO TD", "LIBERACAO TD", "LIBERAÇÃO TD", "CRED.LIBERA",
      "DESCONTO TITULO", "CREDITO ROTATIVO", "ANTECIPACAO RECEBIVEL"),
     "Operacao de Credito - TD"),
    (("EMPRESTIMO", "EMPRÉSTIMO", "FINANCIAMENTO", "CDC", "PARCELA EMP"),
     "Pagamento de Emprestimo"),
    (("CHEQUE ESPECIAL", "LIMITE CONTA"), "Despesa Financeira - Cheque Especial"),
    (("SEGURO", "PRESTAMISTA", "PROTECAO", "PROTEÇÃO"), "Despesa - Seguro"),
]
_REGRAS_APOS_PIX: list[tuple[tuple[str, ...], str]] = [
    (("COMPRA MASTERCARD", "COMPRA VISA", "COMPRA CARTAO", "COMPRA ELO",
      "COMPRA HIPERCARD", "COMPRA AMEX", "COMPRA DEBITO", "DEBITO COMPRA"),
     "Compra Cartao"),
    (("FATURA CARTAO", "PAGTO FATURA", "PAGAMENTO CARTAO CRED"), "Pagamento Fatura Cartao"),
    (("PEDAGIO", "PEDÁGIO", "SICOOB TAG", "SEM PARAR", "MOVE MAIS", "CONECTCAR"),
     "Despesa - Pedagio"),
    (("POSTO ", "COMBUSTIVEL", "GASOLINA", "ETANOL", "DIESEL", "SHELL", "IPIRANGA"),
     "Despesa - Combustivel"),
    (("TARIFA", "MENSALIDADE", "ANUIDADE", "CESTA ", "PACOTE ", "MANUTENCAO",
      "MANUTENÇÃO CONTA"),
     "Despesa Bancaria - Tarifa"),
    (("BOLETO", "COBRAN", "COMPE", "COMPENSADO", "TITULO PAGO"), "Pagamento Boleto"),
    (("SALARIO", "SALÁRIO", "FOLHA PGTO", "PAGAMENTO FOLHA", "PROVENTO", "ADIANTAMENTO SAL"),
     "Folha de Pagamento"),
    (("PRO LABORE", "PRÓ-LABORE", "PRO-LABORE", "RETIRADA SOCIO"),
     "Pro-Labore / Retirada Socio"),
    (("ALUGUEL", "CONDOMINIO", "CONDOMÍNIO"), "Despesa - Aluguel/Condominio"),
    (("ENERGIA ELETRICA", "ENERGIA ELÉTRICA", "ENEL", "CEMIG", "COELBA", "COPEL",
      "CELPE", "CELESC", "ELEKTRO", "LIGHT", "EQUATORIAL"),
     "Despesa - Energia Eletrica"),
    (("AGUA", "ÁGUA", "SABESP", "CEDAE", "COPASA", "EMBASA", "SANEPAR"), "Despesa - Agua"),
    (("TELEFON", "VIVO", "CLARO", "OI ", "TIM ", "INTERNET", "OPERADORA"),
     "Despesa - Telecom"),
    (("SAQUE", "RETIRADA"), "Saque"),
    (("DEPOSITO", "DEPÓSITO"), "Deposito em Dinheiro"),
    (("ESTORNO", "DEVOLUC"), "Estorno"),
]


def _classificar(memo: str, nome: str) -> str:
    """Classificacao contabil heuristica multi-banco."""
    s = f"{memo} {nome}".upper()
    match = lambda *t: any(x in s for x in t)

    for termos, cat in _REGRAS_ANTES_PIX:
        if any(t in s for t in termos):
            return cat

    if "PIX" in s:
        if match("EMITIDO", "ENVIADO", "PAGAMENTO PIX", "PIX SAIDA", "DEBITO PIX"):
            return "Pagamento PIX - Fornecedor/Despesa"
        if match("RECEB", "CREDITO PIX", "CRÉDITO PIX", "PIX ENTRADA", "PIX RECEBIDO"):
            return "Receita PIX"
        return "PIX - A classificar"

    if match("TED ", "DOC "):
        if match("RECEB", "CREDITO", "CRÉDITO"):
            return "Receita TED/DOC"
        return "Pagamento TED/DOC"

    for termos, cat in _REGRAS_APOS_PIX:
        if any(t in s for t in termos):
            return cat

    return "A classificar"


# ── Detector de anomalias ────────────────────────────────────────────────────

def _detectar_anomalias(extratos: list[dict]) -> list[dict]:
    """Identifica anomalias com severidade (critico/alerta/atencao)."""
    anomalias: list[dict] = []

    # Duplicidades
    for e in extratos:
        contagem = Counter(
            (t["data"], round(t["valor"], 2), t["memo"][:40]) for t in e["transacoes"]
        )
        for (data, valor, memo), n in contagem.items():
            if n < 2:
                continue
            sev = "critico" if n >= 3 else "alerta"
            anomalias.append({
                "severidade": sev,
                "tipo": "Duplicidade",
                "titulo": f"{n}x lançamento idêntico em {data}",
                "conta": e["conta"],
                "valor": valor,
                "detalhe": f"R$ {valor:,.2f} | {memo} | {n} ocorrências",
            })

    # Transacoes atipicas
    for e in extratos:
        for t in e["transacoes"]:
            v = abs(t["valor"])
            memo = (t["memo"] or t["nome"])[:60]
            if v > 50000:
                anomalias.append({
                    "severidade": "alerta", "tipo": "Valor alto",
                    "titulo": f"Transação de R$ {v:,.2f}",
                    "conta": e["conta"], "valor": t["valor"],
                    "detalhe": f"{t['data']} | {memo}",
                })
            elif v > 10000:
                anomalias.append({
                    "severidade": "atencao", "tipo": "Valor alto",
                    "titulo": f"Transação de R$ {v:,.2f}",
                    "conta": e["conta"], "valor": t["valor"],
                    "detalhe": f"{t['data']} | {memo}",
                })

    # Estornos
    for e in extratos:
        for t in e["transacoes"]:
            s = (t["memo"] + t["nome"]).upper()
            if "ESTORNO" in s:
                anomalias.append({
                    "severidade": "critico", "tipo": "Estorno",
                    "titulo": "Operação estornada",
                    "conta": e["conta"], "valor": t["valor"],
                    "detalhe": f"{t['data']} | R$ {t['valor']:,.2f} | {t['memo'][:60]}",
                })

    # Transferencias internas sem par
    _KEYWORDS_TRANSF = ("INTERCREDIS", "TRANSF.CONTAS", "TRANSF MESMA TIT", "TRANSFERENCIA ENTRE CONTAS")
    if len(extratos) >= 2:
        for c1, c2 in combinations(extratos, 2):
            def _eh_transf(t):
                s = (t["memo"] + t["nome"]).upper()
                return any(k in s for k in _KEYWORDS_TRANSF)
            tx1 = [t for t in c1["transacoes"] if _eh_transf(t)]
            tx2 = [t for t in c2["transacoes"] if _eh_transf(t)]
            usados: set[int] = set()
            casados = 0
            for t1 in tx1:
                for j, t2 in enumerate(tx2):
                    if j in usados:
                        continue
                    if abs(abs(t1["valor"]) - abs(t2["valor"])) < 0.01 and t1["valor"] * t2["valor"] < 0:
                        usados.add(j); casados += 1; break
            sem_par = (len(tx1) - casados) + (len(tx2) - casados)
            if sem_par > 0:
                anomalias.append({
                    "severidade": "alerta", "tipo": "Transferencia sem par",
                    "titulo": f"{sem_par} transferência(s) interna(s) sem par",
                    "conta": f"{c1['conta']} ↔ {c2['conta']}", "valor": 0,
                    "detalhe": (
                        f"{c1['conta']}: {len(tx1) - casados} sem par | "
                        f"{c2['conta']}: {len(tx2) - casados} sem par"
                    ),
                })

    ordem = {"critico": 0, "alerta": 1, "atencao": 2}
    anomalias.sort(key=lambda a: (ordem[a["severidade"]], -abs(a.get("valor", 0))))
    return anomalias


# ── Estatisticas ─────────────────────────────────────────────────────────────

def _top_categorias_e_contrapartes(extratos: list[dict]) -> dict:
    """Retorna estatisticas: categorias, top contrapartes, evolucao diaria."""
    cats: dict[str, dict] = defaultdict(lambda: {"qtd": 0, "valor": 0.0, "transacoes": []})
    contrapartes: dict[str, dict] = defaultdict(lambda: {"qtd": 0, "valor": 0.0})
    diario: dict[str, dict] = defaultdict(lambda: {"cred": 0.0, "deb": 0.0})

    rx_cnpj = re.compile(r"(\d{2}\.\d{3}\.\d{3}[/ ]?\d{4}[- ]?\d{2})")
    rx_cpf = re.compile(r"(\*{3}\.\d{3}\.\d{3}-\*{2})")

    for e in extratos:
        for t in e["transacoes"]:
            c = _classificar(t["memo"], t["nome"])
            cats[c]["qtd"] += 1
            cats[c]["valor"] += t["valor"]
            cats[c]["transacoes"].append(t)

            texto = f"{t['memo']} {t['nome']}"
            m_cnpj = rx_cnpj.search(texto)
            m_cpf = rx_cpf.search(texto)
            chave = None
            if m_cnpj:
                chave = m_cnpj.group(1).strip()
            elif m_cpf:
                chave = m_cpf.group(1).strip()
            elif t["nome"]:
                chave = t["nome"][:30].strip()
            if chave:
                contrapartes[chave]["qtd"] += 1
                contrapartes[chave]["valor"] += t["valor"]

            if t["valor"] > 0:
                diario[t["data"]]["cred"] += t["valor"]
            else:
                diario[t["data"]]["deb"] += t["valor"]

    return {"cats": dict(cats), "contrapartes": dict(contrapartes), "diario": dict(diario)}


# ── CSV helper para prompts LLM ──────────────────────────────────────────────

def _fmt_csv(transacoes: list[dict]) -> str:
    """Formata transacoes como CSV compacto para enviar ao LLM."""
    linhas = ["data,tipo,valor,memo,nome,checknum"]
    for t in transacoes:
        memo = t["memo"].replace(",", " ").replace("\n", " ")
        nome = t["nome"].replace(",", " ").replace("\n", " ")
        linhas.append(
            f"{t['data']},{t['tipo']},{t['valor']:.2f},{memo},{nome},{t['checknum']}"
        )
    return "\n".join(linhas)
