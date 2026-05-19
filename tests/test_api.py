"""Testes pytest da API de Conciliacao."""
import io
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Forca data dir temporario antes de importar app
os.environ["ORGCONC_DATA_DIR"] = str(Path(__file__).resolve().parent / "_data_test")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api.main import app, _parse_ofx, _parse_xml, _classificar, _detectar_anomalias, _gerar_xlsx, _render_html

client = TestClient(app)

OFX_SAMPLE = """OFXHEADER:100
DATA:OFXSGML
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKACCTFROM>
<BRANCHID>1234-5</BRANCHID>
<ACCTID>9999-9</ACCTID>
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT</TRNTYPE>
<DTPOSTED>20260415120000</DTPOSTED>
<TRNAMT>1500.00</TRNAMT>
<MEMO>PIX RECEBIDO TESTE</MEMO>
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260417120000</DTPOSTED>
<TRNAMT>-89.90</TRNAMT>
<MEMO>TARIFA BANCARIA</MEMO>
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260417120000</DTPOSTED>
<TRNAMT>-89.90</TRNAMT>
<MEMO>TARIFA BANCARIA</MEMO>
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT</TRNTYPE>
<DTPOSTED>20260417120000</DTPOSTED>
<TRNAMT>-89.90</TRNAMT>
<MEMO>TARIFA BANCARIA</MEMO>
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    j = r.json()
    assert "endpoints" in j


def test_logo_base64():
    r = client.get("/logo-base64")
    assert r.status_code == 200
    # Pode estar vazio se logo nao existir, mas a chave deve existir
    assert "data_uri" in r.json()


def test_parser_ofx():
    txs = _parse_ofx(OFX_SAMPLE)
    assert len(txs) == 4
    assert txs[0]["valor"] == 1500.00
    assert txs[0]["tipo"] == "CREDIT"
    assert txs[1]["valor"] == -89.90


def test_parser_xml_camt053():
    xml = """<?xml version="1.0"?>
    <Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
      <BkToCstmrStmt>
        <Stmt>
          <Acct><Id><Othr><Id>ACC-TEST-123</Id></Othr></Id></Acct>
          <Ntry>
            <Amt Ccy="BRL">500.00</Amt>
            <CdtDbtInd>CRDT</CdtDbtInd>
            <BookgDt><Dt>2026-04-15</Dt></BookgDt>
            <NtryDtls><TxDtls><RmtInf><Ustrd>Receita teste</Ustrd></RmtInf></TxDtls></NtryDtls>
          </Ntry>
          <Ntry>
            <Amt Ccy="BRL">75.50</Amt>
            <CdtDbtInd>DBIT</CdtDbtInd>
            <BookgDt><Dt>2026-04-16</Dt></BookgDt>
            <NtryDtls><TxDtls><RmtInf><Ustrd>Pagamento teste</Ustrd></RmtInf></TxDtls></NtryDtls>
          </Ntry>
        </Stmt>
      </BkToCstmrStmt>
    </Document>"""
    txs = _parse_xml(xml, "test.xml")
    assert len(txs) == 2
    assert txs[0]["valor"] == 500.00
    assert txs[1]["valor"] == -75.50


def test_classificador():
    assert _classificar("PIX EMITIDO OUTRA IF", "Fornecedor X") == "Pagamento PIX - Fornecedor/Despesa"
    assert _classificar("PIX RECEBIDO", "Cliente Y") == "Receita PIX"
    assert _classificar("TARIFA MANUTENCAO CONTA", "") == "Despesa Bancaria - Tarifa"
    assert _classificar("DEB.IOF TD", "") == "Despesa Financeira - IOF"
    assert _classificar("DAS SIMPLES NACIONAL", "") == "Tributo"
    assert _classificar("FOLHA PGTO ABRIL", "") == "Folha de Pagamento"
    assert _classificar("BOLETO ENERGIA ELETRICA CEMIG", "") in ("Despesa - Energia Eletrica", "Pagamento Boleto")
    assert _classificar("ALUGUEL ESCRITORIO", "") == "Despesa - Aluguel/Condominio"
    assert _classificar("POSTO IPIRANGA COMPRA", "") in ("Despesa - Combustivel", "Compra Cartao")


def test_deteccao_anomalias_duplicidades():
    txs = _parse_ofx(OFX_SAMPLE)
    extrato = {"conta": "AG 1234-5 / CC 9999-9", "qtd": len(txs), "transacoes": txs, "arquivo": "test.ofx"}
    anomalias = _detectar_anomalias([extrato])
    # Espera detectar a triplicata de TARIFA BANCARIA (3 lancamentos identicos)
    crits = [a for a in anomalias if a["severidade"] == "critico" and a["tipo"] == "Duplicidade"]
    assert len(crits) >= 1


def test_conciliar_ofx_simulacao():
    r = client.post(
        "/conciliar/ofx?simular=true",
        files=[("arquivos", ("test.ofx", OFX_SAMPLE, "application/x-ofx"))],
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["modo"] == "simulacao_local"
    assert "report_id" in j
    assert len(j["extratos"]) == 1
    assert "anomalias" in j
    assert "relatorio_md" in j
    assert "relatorio_html" in j


def test_export_html_xlsx():
    # Gera dataset
    r = client.post(
        "/conciliar/ofx?simular=true",
        files=[("arquivos", ("test.ofx", OFX_SAMPLE, "application/x-ofx"))],
    )
    rid = r.json()["report_id"]
    # HTML
    r_html = client.get(f"/export/html/{rid}")
    assert r_html.status_code == 200
    assert b"ORGATEC" in r_html.content
    assert b"<table" in r_html.content
    # XLSX
    r_xlsx = client.get(f"/export/xlsx/{rid}")
    assert r_xlsx.status_code == 200
    assert r_xlsx.content[:2] == b"PK"  # zip magic (xlsx)


def test_export_id_invalido():
    r = client.get("/export/html/INVALID")
    assert r.status_code == 400


def test_export_id_inexistente():
    r = client.get("/export/html/abcdef012345")
    assert r.status_code == 404


def test_upload_extensao_invalida():
    r = client.post(
        "/conciliar/ofx?simular=true",
        files=[("arquivos", ("malicioso.exe", b"binarylixo", "application/octet-stream"))],
    )
    assert r.status_code == 400
    assert "nao suportada" in r.json()["detail"].lower() or "suport" in r.json()["detail"].lower()


def test_gerar_xlsx_estrutura():
    txs = _parse_ofx(OFX_SAMPLE)
    extrato = {"conta": "AG 1234-5 / CC 9999-9", "qtd": len(txs), "transacoes": txs, "arquivo": "test.ofx"}
    anomalias = _detectar_anomalias([extrato])
    blob = _gerar_xlsx([extrato], anomalias)
    assert blob[:2] == b"PK"  # xlsx valido

    # Abre e verifica abas
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(blob))
    assert "Resumo" in wb.sheetnames
    assert "Transações" in wb.sheetnames
    assert "Anomalias" in wb.sheetnames


def test_render_html_contem_logo_e_dados():
    md = "# Relatorio\n\n| col | val |\n|---|---|\n| a | 1 |\n"
    html = _render_html(md)
    assert "ORGATEC" in html
    assert "Inter:wght" in html
    assert "<table" in html
