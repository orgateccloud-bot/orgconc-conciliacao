"""Testes para api/parsers/xml_parser.py — parser de extratos bancários XML.

Cobre os dois formatos suportados:
- CAMT.053 (ISO 20022, com/sem namespace, padrão bancário brasileiro)
- OFX em XML (STMTTRN), usado como fallback quando não há <Ntry>

Lógica pura, sem DB. pytest puro (sync).
"""
from __future__ import annotations

from api.parsers.xml_parser import _parse_xml


# ────────────────────────────────────────────────────────────────────────
# Fixtures CAMT.053
# ────────────────────────────────────────────────────────────────────────


def _camt(ntries: str, acct: str = "", ns: bool = False) -> str:
    """Monta um documento CAMT.053 mínimo com as <Ntry> fornecidas."""
    xmlns = (
        ' xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"' if ns else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document{xmlns}>
  <BkToCstmrStmt>
    <Stmt>
      {acct}
      {ntries}
    </Stmt>
  </BkToCstmrStmt>
</Document>"""


def _ntry(
    amt: str = "100.00",
    cdtdbt: str = "CRDT",
    bookg_dt: str | None = "2026-05-10",
    val_dt: str | None = None,
    addtl: str | None = "Pagamento recebido",
    ustrd: str | None = None,
    sts: str | None = None,
) -> str:
    partes = ["<Ntry>"]
    if sts is not None:
        partes.append(f"<Sts>{sts}</Sts>")
    if amt is not None:
        partes.append(f"<Amt Ccy=\"BRL\">{amt}</Amt>")
    if cdtdbt is not None:
        partes.append(f"<CdtDbtInd>{cdtdbt}</CdtDbtInd>")
    if bookg_dt is not None:
        partes.append(f"<BookgDt><Dt>{bookg_dt}</Dt></BookgDt>")
    if val_dt is not None:
        partes.append(f"<ValDt><Dt>{val_dt}</Dt></ValDt>")
    detalhe = ""
    if addtl is not None:
        detalhe += f"<AddtlNtryInf>{addtl}</AddtlNtryInf>"
    if ustrd is not None:
        detalhe += f"<NtryDtls><TxDtls><RmtInf><Ustrd>{ustrd}</Ustrd></RmtInf></TxDtls></NtryDtls>"
    if detalhe:
        partes.append(detalhe)
    partes.append("</Ntry>")
    return "".join(partes)


# ────────────────────────────────────────────────────────────────────────
# CAMT.053 — caminho feliz
# ────────────────────────────────────────────────────────────────────────


def test_camt_credito_basico():
    xml = _camt(_ntry(amt="250.50", cdtdbt="CRDT"))
    txs = _parse_xml(xml, "extrato.xml")
    assert len(txs) == 1
    t = txs[0]
    assert t["valor"] == 250.50
    assert t["tipo"] == "CREDIT"
    assert t["data"] == "2026-05-10"
    assert t["memo"] == "Pagamento recebido"
    assert t["nome"] == ""
    assert t["checknum"] == ""
    # sem conta no XML → usa default com o filename
    assert t["conta"] == "XML (extrato.xml)"


def test_camt_debito_vira_valor_negativo():
    xml = _camt(_ntry(amt="80.00", cdtdbt="DBIT"))
    txs = _parse_xml(xml, "x.xml")
    assert len(txs) == 1
    assert txs[0]["valor"] == -80.0
    assert txs[0]["tipo"] == "DEBIT"


def test_camt_debito_com_amt_ja_negativo_normaliza():
    """DBIT força -abs(): mesmo Amt negativo deve permanecer negativo (não inverter)."""
    xml = _camt(_ntry(amt="-80.00", cdtdbt="DBIT"))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["valor"] == -80.0


def test_camt_multiplas_entradas():
    xml = _camt(
        _ntry(amt="100.00", cdtdbt="CRDT", addtl="A")
        + _ntry(amt="40.00", cdtdbt="DBIT", addtl="B")
        + _ntry(amt="10.00", cdtdbt="CRDT", addtl="C")
    )
    txs = _parse_xml(xml, "x.xml")
    assert [t["valor"] for t in txs] == [100.0, -40.0, 10.0]
    assert [t["memo"] for t in txs] == ["A", "B", "C"]


# ────────────────────────────────────────────────────────────────────────
# CAMT.053 — namespace
# ────────────────────────────────────────────────────────────────────────


def test_camt_com_namespace_e_removido():
    xml = _camt(_ntry(amt="55.00", cdtdbt="CRDT"), ns=True)
    txs = _parse_xml(xml, "ns.xml")
    assert len(txs) == 1
    assert txs[0]["valor"] == 55.0


# ────────────────────────────────────────────────────────────────────────
# CAMT.053 — extração da conta (todos os xpaths de fallback)
# ────────────────────────────────────────────────────────────────────────


def test_conta_via_acct_id_othr_id():
    acct = "<Acct><Id><Othr><Id> 12345-6 </Id></Othr></Id></Acct>"
    xml = _camt(_ntry(), acct=acct)
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["conta"] == "Conta 12345-6"


def test_conta_via_acct_id_iban():
    # Sem Othr/Id; cai no segundo xpath .//Acct/Id (que tem texto direto? não:
    # aqui usamos IBAN como filho de Id). Garantimos texto direto em Acct/Id.
    acct = "<Acct><Id>BR123</Id></Acct>"
    xml = _camt(_ntry(), acct=acct)
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["conta"] == "Conta BR123"


def test_conta_default_quando_acct_sem_texto():
    """Acct existe mas sem texto utilizável → mantém o default."""
    acct = "<Acct><Id><Othr></Othr></Id></Acct>"
    xml = _camt(_ntry(), acct=acct)
    txs = _parse_xml(xml, "vazia.xml")
    assert txs[0]["conta"] == "XML (vazia.xml)"


# ────────────────────────────────────────────────────────────────────────
# CAMT.053 — datas (BookgDt preferida, fallback ValDt)
# ────────────────────────────────────────────────────────────────────────


def test_data_usa_bookgdt_quando_presente():
    xml = _camt(_ntry(bookg_dt="2026-01-02", val_dt="2099-12-31"))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["data"] == "2026-01-02"


def test_data_fallback_valdt_quando_sem_bookgdt():
    xml = _camt(_ntry(bookg_dt=None, val_dt="2026-03-04"))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["data"] == "2026-03-04"


def test_data_truncada_em_10_chars():
    """Datetime ISO completo é truncado para AAAA-MM-DD."""
    xml = _camt(_ntry(bookg_dt="2026-07-08T13:45:00-03:00"))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["data"] == "2026-07-08"


# ────────────────────────────────────────────────────────────────────────
# CAMT.053 — memo (AddtlNtryInf preferida, fallback RmtInf/Ustrd)
# ────────────────────────────────────────────────────────────────────────


def test_memo_fallback_para_ustrd():
    xml = _camt(_ntry(addtl=None, ustrd="  PIX recebido  "))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["memo"] == "PIX recebido"


def test_memo_vazio_quando_sem_info():
    xml = _camt(_ntry(addtl=None, ustrd=None))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["memo"] == ""


def test_memo_addtl_tem_prioridade_sobre_ustrd():
    xml = _camt(_ntry(addtl="DETALHE", ustrd="IGNORADO"))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["memo"] == "DETALHE"


# ────────────────────────────────────────────────────────────────────────
# CAMT.053 — entradas puladas / inválidas
# ────────────────────────────────────────────────────────────────────────


def test_pula_entrada_pendente_pdng():
    xml = _camt(
        _ntry(amt="100.00", sts="PDNG")
        + _ntry(amt="200.00", sts="BOOK")
    )
    txs = _parse_xml(xml, "x.xml")
    assert len(txs) == 1
    assert txs[0]["valor"] == 200.0


def test_pula_entrada_pdng_case_insensitive_com_espacos():
    xml = _camt(_ntry(amt="100.00", sts="  pdng  "))
    txs = _parse_xml(xml, "x.xml")
    assert txs == []


def test_pula_entrada_sem_amt():
    xml = _camt(_ntry(amt=None))
    assert _parse_xml(xml, "x.xml") == []


def test_pula_entrada_sem_cdtdbt():
    xml = _camt(_ntry(cdtdbt=None))
    assert _parse_xml(xml, "x.xml") == []


def test_pula_entrada_sem_data():
    xml = _camt(_ntry(bookg_dt=None, val_dt=None))
    assert _parse_xml(xml, "x.xml") == []


def test_pula_entrada_amt_nao_numerico():
    """Amt não numérico (ValueError) → entrada ignorada, sem quebrar o resto."""
    xml = _camt(
        _ntry(amt="abc", cdtdbt="CRDT")
        + _ntry(amt="33.00", cdtdbt="CRDT")
    )
    txs = _parse_xml(xml, "x.xml")
    assert len(txs) == 1
    assert txs[0]["valor"] == 33.0


def test_pula_entrada_amt_vazio_typeerror():
    """Amt sem texto (None) → float(None) lança TypeError, entrada ignorada."""
    xml = _camt("<Ntry><Amt></Amt><CdtDbtInd>CRDT</CdtDbtInd><BookgDt><Dt>2026-01-01</Dt></BookgDt></Ntry>")
    assert _parse_xml(xml, "x.xml") == []


def test_valor_zero_e_tipo_debit():
    """valor == 0 não é > 0, então tipo cai em DEBIT (ramo do ternário)."""
    xml = _camt(_ntry(amt="0.00", cdtdbt="CRDT"))
    txs = _parse_xml(xml, "x.xml")
    assert len(txs) == 1
    assert txs[0]["valor"] == 0.0
    assert txs[0]["tipo"] == "DEBIT"


# ────────────────────────────────────────────────────────────────────────
# XML malformado / vazio
# ────────────────────────────────────────────────────────────────────────


def test_xml_malformado_retorna_lista_vazia():
    assert _parse_xml("<Document><Stmt>", "x.xml") == []


def test_xml_texto_nao_xml_retorna_lista_vazia():
    assert _parse_xml("isto nao e xml", "x.xml") == []


def test_xml_string_vazia_retorna_lista_vazia():
    assert _parse_xml("", "x.xml") == []


def test_xml_sem_transacoes_retorna_lista_vazia():
    xml = _camt("")  # Stmt sem Ntry e sem STMTTRN
    assert _parse_xml(xml, "x.xml") == []


# ────────────────────────────────────────────────────────────────────────
# OFX em XML (STMTTRN) — fallback quando não há <Ntry>
# ────────────────────────────────────────────────────────────────────────


def _ofx_xml(stmttrns: str, acctid: str | None = None) -> str:
    acct = f"<ACCTID>{acctid}</ACCTID>" if acctid is not None else ""
    return f"""<?xml version="1.0"?>
<OFX>
  <BANKMSGSRSV1><STMTTRNRS><STMTRS>
    <BANKACCTFROM>{acct}</BANKACCTFROM>
    <BANKTRANLIST>
      {stmttrns}
    </BANKTRANLIST>
  </STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>"""


def _stmttrn(
    trntype: str = "CREDIT",
    dtposted: str = "20260510",
    trnamt: str = "150.00",
    memo: str | None = "Compra cartao",
    name: str | None = "FORNECEDOR LTDA",
    checknum: str | None = "00123",
) -> str:
    partes = [f"<STMTTRN><TRNTYPE>{trntype}</TRNTYPE><DTPOSTED>{dtposted}</DTPOSTED><TRNAMT>{trnamt}</TRNAMT>"]
    if memo is not None:
        partes.append(f"<MEMO>{memo}</MEMO>")
    if name is not None:
        partes.append(f"<NAME>{name}</NAME>")
    if checknum is not None:
        partes.append(f"<CHECKNUM>{checknum}</CHECKNUM>")
    partes.append("</STMTTRN>")
    return "".join(partes)


def test_ofx_xml_basico():
    xml = _ofx_xml(_stmttrn())
    txs = _parse_xml(xml, "extrato_ofx.xml")
    assert len(txs) == 1
    t = txs[0]
    assert t["tipo"] == "CREDIT"
    assert t["data"] == "2026-05-10"
    assert t["valor"] == 150.0
    assert t["memo"] == "Compra cartao"
    assert t["nome"] == "FORNECEDOR LTDA"
    assert t["checknum"] == "00123"


def test_ofx_xml_acctid_define_conta():
    xml = _ofx_xml(_stmttrn(), acctid="987654")
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["conta"] == "Conta 987654"


def test_ofx_xml_valor_negativo_debito():
    xml = _ofx_xml(_stmttrn(trntype="DEBIT", trnamt="-42.50"))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["valor"] == -42.50
    assert txs[0]["tipo"] == "DEBIT"


def test_ofx_xml_trnamt_invalido_pula_entrada():
    xml = _ofx_xml(_stmttrn(trnamt="nan-invalido") + _stmttrn(trnamt="9.00"))
    txs = _parse_xml(xml, "x.xml")
    assert len(txs) == 1
    assert txs[0]["valor"] == 9.0


def test_ofx_xml_campos_ausentes_viram_defaults():
    """Sem MEMO/NAME/CHECKNUM/TRNTYPE/DTPOSTED → strings vazias e zero seguros."""
    xml = """<?xml version="1.0"?>
<OFX><BANKTRANLIST>
  <STMTTRN></STMTTRN>
</BANKTRANLIST></OFX>"""
    txs = _parse_xml(xml, "x.xml")
    assert len(txs) == 1
    t = txs[0]
    assert t["tipo"] == ""
    assert t["data"] == ""  # DTPOSTED ausente → "" (len != 8)
    assert t["valor"] == 0.0  # TRNAMT ausente → float(0)
    assert t["memo"] == ""
    assert t["nome"] == ""
    assert t["checknum"] == ""


def test_ofx_xml_dtposted_curto_nao_formata():
    """DTPOSTED com tamanho != 8 não é reformatado em ISO (fica como veio truncado)."""
    xml = _ofx_xml(_stmttrn(dtposted="2026"))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["data"] == "2026"


def test_ofx_xml_dtposted_com_hora_trunca_para_8():
    """DTPOSTED com hora (ex.: 20260510120000) é truncado para 8 e formatado ISO."""
    xml = _ofx_xml(_stmttrn(dtposted="20260510120000[-3:BRT]"))
    txs = _parse_xml(xml, "x.xml")
    assert txs[0]["data"] == "2026-05-10"


def test_ofx_xml_multiplas_transacoes():
    xml = _ofx_xml(
        _stmttrn(trnamt="10.00", memo="A")
        + _stmttrn(trnamt="-5.00", memo="B")
    )
    txs = _parse_xml(xml, "x.xml")
    assert [t["valor"] for t in txs] == [10.0, -5.0]


def test_ntry_tem_prioridade_sobre_stmttrn():
    """Se houver Ntry válida, STMTTRN não é processado (bloco só roda se vazio)."""
    xml = f"""<?xml version="1.0"?>
<Document><Stmt>
  {_ntry(amt="77.00", cdtdbt="CRDT")}
  {_stmttrn(trnamt="999.00")}
</Stmt></Document>"""
    txs = _parse_xml(xml, "x.xml")
    assert len(txs) == 1
    assert txs[0]["valor"] == 77.0
