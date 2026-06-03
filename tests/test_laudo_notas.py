"""Testes do Laudo de Documentos Fiscais (serviço + endpoint /fiscal/laudo-notas)."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("ORGCONC_DATA_DIR", str(Path(__file__).resolve().parent / "_data_test"))
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

from fastapi.testclient import TestClient

from api.main import app
from api.matchers.xml_fiscal import DocumentoFiscalLido
from api.services.laudo_notas import (
    ABAS_NOTAS,
    gerar_laudo_notas_html,
    gerar_laudo_notas_workbook,
)

client = TestClient(app)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _doc(chave="3" * 44, emit_cnpj="12345678000190", nome="FORNECEDOR X",
         valor=1000.0, situacao="AUTORIZADA", chave_valida=True, data="2026-03-10"):
    return DocumentoFiscalLido(
        tipo="NF-e", modelo="55", chave=chave, numero="1", serie="1",
        data_emissao=data, emit_cnpj=emit_cnpj, emit_nome=nome, emit_uf="GO",
        dest_cnpj="99888777000166", dest_nome="DEST", valor_total=valor,
        valor_icms=valor * 0.12, natureza_operacao="VENDA",
        chave_valida=chave_valida, situacao=situacao,
    )


# ── Serviço ─────────────────────────────────────────────────────────────────

def test_workbook_tem_6_abas_e_stats():
    docs = [_doc(chave="a" * 44, valor=1000.0), _doc(chave="b" * 44, valor=500.0, emit_cnpj="98765432000110")]
    wb, stats = gerar_laudo_notas_workbook(docs)
    assert wb.sheetnames == ABAS_NOTAS
    assert stats["total_documentos"] == 2
    assert stats["volume_total"] == 1500.0
    assert stats["fornecedores"] == 2


def test_workbook_conta_alertas():
    docs = [
        _doc(chave="a" * 44, chave_valida=False),                 # chave inválida
        _doc(chave="b" * 44, situacao="CANCELADA"),               # cancelada
        _doc(chave="c" * 44, emit_cnpj="11111111000111"),         # emitente não-ativo (via cadastro)
    ]
    _, stats = gerar_laudo_notas_workbook(docs, situacao_por_cnpj={"11111111000111": "BAIXADA"})
    assert stats["chaves_invalidas"] == 1
    assert stats["canceladas"] == 1
    assert stats["emitentes_nao_ativos"] == 1


def test_workbook_sem_situacao_nao_quebra():
    wb, stats = gerar_laudo_notas_workbook([_doc()])
    assert stats["emitentes_nao_ativos"] == 0
    assert wb.sheetnames == ABAS_NOTAS


def test_html_tem_estrutura_e_stats():
    docs = [_doc(chave="a" * 44, valor=1000.0), _doc(chave="b" * 44, valor=500.0, emit_cnpj="98765432000110")]
    html, stats = gerar_laudo_notas_html(docs)
    assert html.startswith("<!DOCTYPE html>")
    assert "Documentos Fiscais" in html
    assert "Top Fornecedores" in html and "Natureza de Operacao" in html and "Alertas" in html
    # visual do laudo forense (capa + fontes)
    assert "capa" in html and "Playfair Display" in html
    assert stats["total_documentos"] == 2 and stats["volume_total"] == 1500.0


def test_html_escapa_nome_emitente():
    docs = [_doc(nome="<script>alert(1)</script> LTDA")]
    html, _ = gerar_laudo_notas_html(docs)
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


# ── Endpoint ────────────────────────────────────────────────────────────────

def _nfe_xml(numero="1", valor="1500.00", chave="3" * 44):
    return (
        '<?xml version="1.0"?>'
        '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe>'
        f'<infNFe Id="NFe{chave}">'
        f"<ide><mod>55</mod><nNF>{numero}</nNF><serie>1</serie><natOp>VENDA</natOp></ide>"
        "<emit><CNPJ>12345678000190</CNPJ><xNome>FORN</xNome>"
        "<enderEmit><UF>GO</UF></enderEmit></emit>"
        "<dest><CNPJ>99888777000166</CNPJ><xNome>DEST</xNome></dest>"
        "<det><prod><CFOP>5102</CFOP></prod></det>"
        f"<total><ICMSTot><vNF>{valor}</vNF><vICMS>180.00</vICMS></ICMSTot></total>"
        "</infNFe></NFe></nfeProc>"
    ).encode()


def test_endpoint_laudo_notas_xml_valido_retorna_xlsx():
    files = [("arquivos", ("nota.xml", _nfe_xml(), "application/xml"))]
    r = client.post("/fiscal/laudo-notas", files=files)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == _XLSX_MIME
    assert r.content[:2] == b"PK"  # XLSX é um zip
    assert "laudo_notas.xlsx" in r.headers.get("content-disposition", "")


def test_endpoint_laudo_notas_sem_xml_valido_retorna_400():
    files = [("arquivos", ("lixo.xml", b"<nao-fiscal/>", "application/xml"))]
    r = client.post("/fiscal/laudo-notas", files=files)
    assert r.status_code == 400


def test_endpoint_laudo_notas_sem_arquivo_retorna_422():
    # File(...) é obrigatório -> FastAPI valida o corpo
    r = client.post("/fiscal/laudo-notas")
    assert r.status_code == 422


def test_endpoint_laudo_notas_formato_html():
    files = [("arquivos", ("nota.xml", _nfe_xml(), "application/xml"))]
    r = client.post("/fiscal/laudo-notas?formato=html", files=files)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    assert "Documentos Fiscais" in r.text


def test_endpoint_laudo_notas_formato_invalido_400():
    files = [("arquivos", ("nota.xml", _nfe_xml(), "application/xml"))]
    r = client.post("/fiscal/laudo-notas?formato=docx", files=files)
    assert r.status_code == 400
