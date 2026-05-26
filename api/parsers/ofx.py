from __future__ import annotations

import re


def _parse_ofx(text: str) -> list[dict]:
    """Parser OFX minimalista (SGML).

    Suporta tanto OFX com </STMTTRN> quanto SGML padrao bancario BR
    sem tags de fechamento.
    """
    branch_m = re.search(r"<BRANCHID>([^<\n]+)", text)
    acct_m = re.search(r"<ACCTID>([^<\n]+)", text)
    conta = f"AG {branch_m.group(1).strip() if branch_m else '?'} / CC {acct_m.group(1).strip() if acct_m else '?'}"
    transacoes: list[dict] = []

    # Tenta split por par <STMTTRN>...</STMTTRN> (OFX XML-like)
    partes = re.split(r"</?STMTTRN>", text, flags=re.IGNORECASE)
    blocos = partes[1::2]

    # FIX 2: fallback para SGML sem tags de fechamento
    if not blocos:
        blocos = re.split(r"<STMTTRN>", text, flags=re.IGNORECASE)[1:]

    for bloco in blocos:
        def fld(tag: str, _b: str = bloco) -> str:
            m = re.search(rf"<{tag}>([^<\n]*)", _b)
            return m.group(1).strip() if m else ""

        data_raw = fld("DTPOSTED")[:8]
        data = (
            f"{data_raw[:4]}-{data_raw[4:6]}-{data_raw[6:8]}"
            if len(data_raw) == 8 else data_raw
        )
        # FIX 4: extrai FITID
        fitid = fld("FITID")
        transacoes.append({
            "conta": conta,
            "data": data,
            "tipo": fld("TRNTYPE"),
            "valor": float(fld("TRNAMT") or 0),
            "memo": fld("MEMO"),
            "nome": fld("NAME"),
            "checknum": fld("CHECKNUM"),
            "fitid": fitid,
        })
    return transacoes
