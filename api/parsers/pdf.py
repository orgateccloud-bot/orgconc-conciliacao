"""Parser de PDF de extrato bancario com fallback OCR.

Estrategias (em ordem):
1. pdfplumber + 3 regex (sinal D/C, padrao, compacta) sobre texto extraido.
2. Se 0 transacoes E houver paginas sem texto: OCR (Tesseract via PyMuPDF)
   e reaplica regex sobre o texto OCR.

OCR ativado por ORGCONC_OCR_ENABLED=true (default true). Limite de paginas:
ORGCONC_OCR_MAX_PAGES (default 50). Tesseract binary em ORGCONC_TESSERACT_CMD
ou no PATH.
"""
from __future__ import annotations

import io
import logging
import os
import re
from typing import Optional

import pdfplumber
from fastapi import HTTPException

log = logging.getLogger('orgconc.parsers')


# ── Regex pre-compiladas ──────────────────────────────────────────────────

_RX_CONTA = re.compile(
    r"(?:AG[EÊE]?N?CIA|AG[ÊE]?)\s*:?\s*(\d{3,5}[-\d]?)\s+"
    r"(?:CONTA|C\.?C\.?|CC)\s*:?\s*(\d{4,10}[-\d]?)",
    re.IGNORECASE,
)
_RX_SINAL_DC = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+(.{5,80}?)\s+([\d.]+,\d{2})\s*([CD])\b",
    re.IGNORECASE,
)
_RX_PADRAO = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+(.{5,80}?)\s+([+\-]?\s*R?\$?\s*[\d.]+,\d{2})"
)
_RX_COMPACTA = re.compile(
    r"(\d{2}/\d{2}/\d{2,4})\s+(.{3,80}?)\s+(\(?\s*[+\-]?\s*[\d.]+,\d{2}\s*\)?)"
)

_KEYWORDS_DEBITO = (
    "PAGTO", "DEBITO", "DÉBITO", "DEB ", "PIX EMITIDO", "PIX ENVIADO",
    "SAQUE", "COMPRA", "TARIFA", "JUROS", "IOF", "BOLETO", "TED ENVIADA",
    "DOC ENVIADO", "PAGAMENTO", "ESTORNO DEB", "RETIRADA",
)


def _parse_valor(s: str) -> Optional[float]:
    s = s.strip()
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = s.strip("()").replace("R", "").replace("$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".").lstrip("+-")
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def _parse_data(s: str) -> Optional[str]:
    partes = s.split("/")
    if len(partes) != 3:
        return None
    dia, mes, ano = partes
    if len(ano) == 2:
        ano = "20" + ano
    if len(dia) != 2 or len(mes) != 2 or len(ano) != 4:
        return None
    return f"{ano}-{mes}-{dia}"


# ── Pipeline regex reusavel (chamado por OCR tambem) ───────────────────────

def aplicar_regex_em_texto(
    text: str,
    conta: str,
    vistos: Optional[set[tuple[str, float, str]]] = None,
) -> list[dict]:
    """Aplica as 3 estrategias regex sobre uma string de texto.

    Usado em 2 caminhos:
    - texto direto extraido por pdfplumber
    - texto OCR extraido por api/parsers/pdf_ocr.py
    """
    if vistos is None:
        vistos = set()
    transacoes: list[dict] = []

    def _emit(data_iso: str, desc: str, valor: float) -> None:
        chave = (data_iso, round(valor, 2), desc.strip()[:40])
        if chave in vistos:
            return
        vistos.add(chave)
        transacoes.append({
            "conta": conta,
            "data": data_iso,
            "tipo": "CREDIT" if valor > 0 else "DEBIT",
            "valor": valor,
            "memo": desc.strip(),
            "nome": "",
            "checknum": "",
        })

    # 1. Sinal D/C explicito (mais confiavel)
    for m in _RX_SINAL_DC.finditer(text):
        data_br, desc, valor_s, sinal = m.groups()
        data_iso = _parse_data(data_br)
        valor = _parse_valor(valor_s)
        if not data_iso or valor is None:
            continue
        valor = -abs(valor) if sinal.upper() == "D" else abs(valor)
        _emit(data_iso, desc, valor)

    # 2. Padrao com possivel sinal embutido
    for m in _RX_PADRAO.finditer(text):
        data_br, desc, valor_s = m.groups()
        data_iso = _parse_data(data_br)
        valor = _parse_valor(valor_s)
        if not data_iso or valor is None:
            continue
        desc_up = desc.upper()
        if "+" not in valor_s and "-" not in valor_s and "(" not in valor_s:
            if any(k in desc_up for k in _KEYWORDS_DEBITO):
                valor = -abs(valor)
        _emit(data_iso, desc, valor)

    # 3. Compacta (data dd/mm/aa) — so se as anteriores nao acharam nada
    if not transacoes:
        for m in _RX_COMPACTA.finditer(text):
            data_br, desc, valor_s = m.groups()
            data_iso = _parse_data(data_br)
            valor = _parse_valor(valor_s)
            if not data_iso or valor is None:
                continue
            _emit(data_iso, desc, valor)

    return transacoes


# ── Entry point ───────────────────────────────────────────────────────────

def _parse_pdf(content: bytes, filename: str) -> list[dict]:
    """Extrai transacoes. Caminho texto + fallback OCR."""
    conta_default = f"PDF ({filename})"
    conta_detectada: Optional[str] = None
    transacoes: list[dict] = []
    vistos: set[tuple[str, float, str]] = set()

    try:
        paginas_sem_texto: list[int] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            total_paginas = len(pdf.pages)
            for idx, page in enumerate(pdf.pages):
                text = page.extract_text() or ""

                if not text.strip():
                    paginas_sem_texto.append(idx)

                if conta_detectada is None:
                    m_conta = _RX_CONTA.search(text)
                    if m_conta:
                        ag, cc = m_conta.groups()
                        conta_detectada = f"AG {ag} / CC {cc}"

                conta = conta_detectada or conta_default
                transacoes.extend(aplicar_regex_em_texto(text, conta, vistos))

        # Fallback OCR
        ocr_enabled = os.environ.get("ORGCONC_OCR_ENABLED", "true").strip().lower() \
                        not in ("0", "false", "no")
        if not transacoes and paginas_sem_texto and ocr_enabled:
            log.info(
                "PDF %s: 0 transacoes via texto, %d/%d paginas sem texto. Tentando OCR.",
                filename, len(paginas_sem_texto), total_paginas,
            )
            try:
                from api.parsers.pdf_ocr import extrair_via_ocr
                transacoes = extrair_via_ocr(
                    content,
                    filename,
                    paginas_sem_texto,
                    conta_detectada or conta_default,
                )
            except Exception:
                log.exception("OCR fallback falhou para %s", filename)

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Erro parseando PDF %s", filename)
        raise HTTPException(status_code=400, detail=f"PDF invalido ou corrompido: {e}") from e

    log.info("PDF %s: %d transacoes extraidas (final)", filename, len(transacoes))
    return transacoes
