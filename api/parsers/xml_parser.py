from __future__ import annotations

import re
import xml.etree.ElementTree as _ET
import defusedxml.ElementTree as ET

def _parse_xml(text: str, filename: str) -> list[dict]:
    """Extrai transacoes de XML (CAMT.053, padrao bancario brasileiro, ou OFX em XML)."""
    transacoes: list[dict] = []
    conta_default = f"XML ({filename})"
    try:
        root = ET.fromstring(text)
    except _ET.ParseError:
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
        # FIX 5: pula transacoes pendentes (PDNG)
        sts_el = ntry.find("Sts")
        if sts_el is not None and (sts_el.text or "").strip().upper() == "PDNG":
            continue
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
