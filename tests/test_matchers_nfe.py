"""Testes para api/matchers/nfe.py — matcher do estágio 2 (NF-e)."""
from __future__ import annotations

import asyncio
import io
import zipfile

import pytest

from api.matchers.cascata import Resultado, Transacao, classificar, ler_ofx
from api.matchers.nfe import (
    NotaFiscal,
    indexar_bytes,
    ler_nfe_bytes,
    resolver,
)


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────


def _nfe_xml(numero: str, valor: str, chave: str = None, emit_nome: str = "Fornecedor X") -> bytes:
    """Gera um XML mínimo de NF-e válido para o parser agnóstico a namespace."""
    if chave is None:
        chave = numero.zfill(44)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe{chave}">
      <ide>
        <nNF>{numero}</nNF>
        <serie>1</serie>
        <dhEmi>2026-05-10T10:00:00-03:00</dhEmi>
      </ide>
      <emit>
        <CNPJ>12345678000190</CNPJ>
        <xNome>{emit_nome}</xNome>
      </emit>
      <dest>
        <CNPJ>11222333000181</CNPJ>
        <xNome>Cliente Y</xNome>
      </dest>
      <total>
        <ICMSTot>
          <vNF>{valor}</vNF>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>
""".encode("utf-8")


def _resultado_nfe(numero: str, valor: float, memo: str = None) -> Resultado:
    """Helper: cria um Resultado simulando classificação para match_nfe."""
    t = Transacao(
        data="2026-05-10",
        tipo="DEBIT",
        valor=-abs(valor),
        fitid=f"FITID-{numero}",
        memo=memo or f"DEB.TIT nf {numero}",
        nome=f"PAGAMENTO NF {numero}",
    )
    return Resultado(transacao=t, estagio=2, metodo="match_nfe", chave=numero)


# ────────────────────────────────────────────────────────────────────────
# Testes do parser
# ────────────────────────────────────────────────────────────────────────


def test_ler_nfe_bytes_parse_basico():
    xml = _nfe_xml("12345", "1500.00")
    nf = ler_nfe_bytes(xml)
    assert nf is not None
    assert nf.numero == "12345"
    assert nf.valor == 1500.00
    assert nf.emit_cnpj == "12345678000190"
    assert nf.emit_nome == "Fornecedor X"
    assert nf.data_emissao == "2026-05-10"


def test_ler_nfe_bytes_xml_invalido():
    assert ler_nfe_bytes(b"<not-nfe/>") is None
    assert ler_nfe_bytes(b"sem xml") is None


def test_indexar_remove_zeros_a_esquerda():
    xmls = [
        ("nf001.xml", _nfe_xml("0001", "100.00")),
        ("nf2.xml", _nfe_xml("0002", "200.00")),
    ]
    indice = indexar_bytes(xmls)
    assert "1" in indice
    assert "2" in indice
    assert indice["1"][0].valor == 100.00


# ────────────────────────────────────────────────────────────────────────
# Testes do matcher (4 cenários)
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolver_match_exato():
    """RESOLVIDO: número da NF e valor batem exatamente."""
    xmls = [("nf52269.xml", _nfe_xml("52269", "185.73"))]
    res = [_resultado_nfe("52269", 185.73)]
    saida = await resolver(res, xmls)
    assert len(saida) == 1
    assert saida[0].status == "RESOLVIDO"
    assert saida[0].nota.numero == "52269"
    assert saida[0].flag == ""


@pytest.mark.asyncio
async def test_resolver_nf_nao_encontrada():
    """NF_NAO_ENCONTRADA: número não existe no índice de XMLs."""
    xmls = [("nf99.xml", _nfe_xml("99", "10.00"))]
    res = [_resultado_nfe("88888", 999.00)]
    saida = await resolver(res, xmls)
    assert len(saida) == 1
    assert saida[0].status == "NF_NAO_ENCONTRADA"
    assert "88888" in saida[0].flag


@pytest.mark.asyncio
async def test_resolver_nf_ambigua_mesmo_valor():
    """NF_AMBIGUA: 2 NFs com mesmo número e mesmo valor — não há como desempatar."""
    xmls = [
        ("nf1.xml", _nfe_xml("100", "500.00", chave="A" * 44, emit_nome="Forn A")),
        ("nf2.xml", _nfe_xml("100", "500.00", chave="B" * 44, emit_nome="Forn B")),
    ]
    res = [_resultado_nfe("100", 500.00)]
    saida = await resolver(res, xmls)
    assert len(saida) == 1
    assert saida[0].status == "NF_AMBIGUA"
    assert "2 NFs" in saida[0].flag


@pytest.mark.asyncio
async def test_resolver_valor_divergente_com_flag():
    """RESOLVIDO com flag: uma única NF com o número, valor não bate (juros/desconto)."""
    xmls = [("nf500.xml", _nfe_xml("500", "1000.00"))]
    res = [_resultado_nfe("500", 1010.00)]  # 10 a mais (juros)
    saida = await resolver(res, xmls)
    assert len(saida) == 1
    assert saida[0].status == "RESOLVIDO"
    assert saida[0].nota.numero == "500"
    assert "diverge" in saida[0].flag


@pytest.mark.asyncio
async def test_resolver_filtra_so_estagio_2():
    """resolver deve ignorar resultados de outros estágios."""
    t = Transacao(data="2026-05-10", tipo="DEBIT", valor=-100, fitid="x", memo="TARIFA", nome="")
    r_tarifa = Resultado(t, estagio=3, metodo="tarifa_bancaria")
    r_nfe = _resultado_nfe("777", 50.00)
    xmls = [("nf777.xml", _nfe_xml("777", "50.00"))]
    saida = await resolver([r_tarifa, r_nfe], xmls)
    assert len(saida) == 1  # só a NFe
    assert saida[0].status == "RESOLVIDO"


# ────────────────────────────────────────────────────────────────────────
# Teste do classificador (cascata)
# ────────────────────────────────────────────────────────────────────────


def test_classificar_nfe_extrai_numero():
    t = Transacao(
        data="2026-05-10", tipo="DEBIT", valor=-185.73,
        fitid="X1", memo="DEB.TIT.COMPE EFETIVADO", nome="Rsf7j94 nf 52269",
    )
    r = classificar(t)
    assert r.metodo == "match_nfe"
    assert r.chave == "52269"
    assert r.estagio == 2


def test_classificar_transferencia_interna():
    t = Transacao(
        data="2026-05-10", tipo="DEBIT", valor=-2000.00,
        fitid="X2", memo="DEB.TRANSF.CONTAS MESMA TIT",
        nome="FAV.: PROPRIO CLIENTE",
    )
    r = classificar(t)
    assert r.metodo == "transferencia_interna"
    assert r.estagio == 0


def test_classificar_tarifa():
    t = Transacao(
        data="2026-05-10", tipo="DEBIT", valor=-4.40,
        fitid="X3", memo="TARIFA COBRANCA", nome="",
    )
    r = classificar(t)
    assert r.metodo == "tarifa_bancaria"
    assert r.estagio == 3


def test_classificar_tributo_darf():
    t = Transacao(
        data="2026-05-10", tipo="DEBIT", valor=-1234.56,
        fitid="X4", memo="DARF PAGAMENTO", nome="DARF PARCELAMENTO DIFAL",
    )
    r = classificar(t)
    assert r.metodo == "match_guia_tributo"
    assert r.chave == "DARF"
    assert r.estagio == 4


def test_classificar_cnpj_explicito():
    t = Transacao(
        data="2026-05-10", tipo="DEBIT", valor=-800.00,
        fitid="X5", memo="PIX EMITIDO OUTRA IF",
        nome="Pagamento Pix 11.222.333/0001-81",
    )
    r = classificar(t)
    assert r.metodo == "match_documento"
    assert r.chave == "11222333000181"
    assert r.estagio == 1


# ────────────────────────────────────────────────────────────────────────
# Teste do adapter ler_ofx (integração com api/parsers/ofx.py)
# ────────────────────────────────────────────────────────────────────────


def test_ler_ofx_adapter():
    """ler_ofx deve aceitar bytes de OFX e devolver list[Transacao]."""
    ofx = b"""OFXHEADER:100
DATA:OFXSGML

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260510
<TRNAMT>-185.73
<FITID>X296461
<NAME>Rsf7j94 nf 52269
<MEMO>DEB.TIT.COMPE EFETIVADO
</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""
    txs = ler_ofx(ofx)
    assert len(txs) >= 1
    t = txs[0]
    assert t.fitid == "X296461"
    assert abs(t.valor + 185.73) < 0.001
    assert "52269" in t.nome


# ────────────────────────────────────────────────────────────────────────
# Teste end-to-end: extração de ZIP + matching
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_completo_zip():
    """End-to-end mini: OFX + ZIP de XMLs → resolver."""
    xml1 = _nfe_xml("52269", "185.73", emit_nome="Fornecedor Rsf7j94")
    xml2 = _nfe_xml("2447", "2000.00", emit_nome="Fornecedor RMB4A64")

    # Simula extração de ZIP em memória (como o router faria)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("nf52269.xml", xml1)
        zf.writestr("nf2447.xml", xml2)

    # Decodifica o ZIP e separa
    buf.seek(0)
    xmls = []
    with zipfile.ZipFile(buf) as zf:
        for name in zf.namelist():
            with zf.open(name) as fh:
                xmls.append((name, fh.read()))

    assert len(xmls) == 2

    res = [
        _resultado_nfe("52269", 185.73),
        _resultado_nfe("2447", 2000.00),
    ]
    saida = await resolver(res, xmls)
    assert len(saida) == 2
    assert all(s.status == "RESOLVIDO" for s in saida)
