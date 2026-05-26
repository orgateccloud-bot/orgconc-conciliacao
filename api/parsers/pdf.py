from __future__ import annotations

import io
import logging
import re
from typing import Optional

import pdfplumber
from fastapi import HTTPException

log = logging.getLogger('orgconc.parsers')


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
            # FIX 3: vistos deve ser por extrato (fora do loop de paginas)
            # para deduplicar transacoes identicas entre paginas adjacentes
            vistos: set = set()
            for page in pdf.pages:
                text = page.extract_text() or ""
                if conta_detectada is None:
                    m_conta = rx_conta.search(text)
                    if m_conta:
                        ag, cc = m_conta.groups()
                        conta_detectada = f"AG {ag} / CC {cc}"


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
