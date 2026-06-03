"""Testes para api/matchers/xml_fiscal.py — parser unificado NF-e/CT-e/NFS-e."""
from __future__ import annotations

import io
import zipfile


from api.matchers.xml_fiscal import (
    detectar_e_parsear,
    extrair_xmls_zip,
    parse_cte,
    parse_lote_xmls,
    parse_nfe,
    parse_nfse,
    validar_chave_acesso,
)


def _chave_com_dv(corpo43: str) -> str:
    """Acrescenta o DV mod-11 correto a 43 dígitos (mesmo algoritmo da SEFAZ)."""
    peso, soma = 2, 0
    for d in reversed(corpo43):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    dv = 0 if resto in (0, 1) else 11 - resto
    return corpo43 + str(dv)


def test_validar_chave_acesso_mod11():
    valida = _chave_com_dv("1" * 43)
    assert len(valida) == 44
    assert validar_chave_acesso(valida) is True
    # ignora prefixo textual e formatação
    assert validar_chave_acesso("NFe" + valida) is True
    # DV corrompido -> inválida
    dv_errado = str((int(valida[-1]) + 1) % 10)
    assert validar_chave_acesso(valida[:43] + dv_errado) is False
    # tamanho errado -> inválida
    assert validar_chave_acesso("123") is False
    assert validar_chave_acesso("") is False


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────


def _nfe_xml(numero="123", valor="1500.00", chave=None, modelo="55") -> bytes:
    if chave is None:
        chave = numero.zfill(44)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe{chave}">
      <ide>
        <mod>{modelo}</mod>
        <nNF>{numero}</nNF>
        <serie>1</serie>
        <dhEmi>2026-05-10T10:00:00-03:00</dhEmi>
        <natOp>VENDA</natOp>
      </ide>
      <emit>
        <CNPJ>12345678000190</CNPJ>
        <xNome>Fornecedor Teste</xNome>
        <enderEmit><UF>GO</UF><xMun>Goiania</xMun></enderEmit>
      </emit>
      <dest>
        <CNPJ>99888777000166</CNPJ>
        <xNome>EMPRESA EXEMPLO</xNome>
      </dest>
      <total>
        <ICMSTot>
          <vNF>{valor}</vNF>
          <vICMS>180.00</vICMS>
          <vPIS>24.75</vPIS>
          <vCOFINS>114.00</vCOFINS>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>
""".encode("utf-8")


def _cte_xml(numero="999", valor="2500.00", chave=None) -> bytes:
    if chave is None:
        chave = ("57" + numero).zfill(44)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cteProc xmlns="http://www.portalfiscal.inf.br/cte">
  <CTe>
    <infCte Id="CTe{chave}">
      <ide>
        <mod>57</mod>
        <nCT>{numero}</nCT>
        <serie>1</serie>
        <dhEmi>2026-04-15T10:00:00-03:00</dhEmi>
        <natOp>PRESTACAO TRANSPORTE</natOp>
        <UFIni>GO</UFIni>
      </ide>
      <emit>
        <CNPJ>99888777000166</CNPJ>
        <xNome>TRANSPORTADORA EXEMPLO</xNome>
        <enderEmit><UF>GO</UF></enderEmit>
      </emit>
      <rem>
        <CNPJ>11111111000111</CNPJ>
        <xNome>Remetente</xNome>
      </rem>
      <dest>
        <CNPJ>22222222000122</CNPJ>
        <xNome>Destinatario</xNome>
      </dest>
      <vPrest>
        <vTPrest>{valor}</vTPrest>
      </vPrest>
    </infCte>
  </CTe>
</cteProc>
""".encode("utf-8")


def _nfse_xml(numero="42", valor="800.00") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<CompNfse>
  <Nfse>
    <InfNfse>
      <Numero>{numero}</Numero>
      <DataEmissao>2026-03-10</DataEmissao>
      <PrestadorServico>
        <IdentificacaoPrestador>
          <CpfCnpj><Cnpj>33333333000133</Cnpj></CpfCnpj>
        </IdentificacaoPrestador>
        <RazaoSocial>Prestador NFSe</RazaoSocial>
      </PrestadorServico>
      <TomadorServico>
        <IdentificacaoTomador>
          <CpfCnpj><Cnpj>99888777000166</Cnpj></CpfCnpj>
        </IdentificacaoTomador>
        <RazaoSocial>Tomador</RazaoSocial>
      </TomadorServico>
      <Servico>
        <Valores>
          <ValorServicos>{valor}</ValorServicos>
          <ValorIss>40.00</ValorIss>
          <ValorPis>5.28</ValorPis>
          <ValorCofins>24.32</ValorCofins>
        </Valores>
      </Servico>
    </InfNfse>
  </Nfse>
</CompNfse>
""".encode("utf-8")


# ────────────────────────────────────────────────────────────────────────
# parse_nfe
# ────────────────────────────────────────────────────────────────────────


def test_parse_nfe_basico():
    doc = parse_nfe(_nfe_xml(numero="123", valor="1500.00"))
    assert doc is not None
    assert doc.tipo == "NF-e"
    assert doc.modelo == "55"
    assert doc.numero == "123"
    assert doc.valor_total == 1500.0
    assert doc.emit_cnpj == "12345678000190"
    assert doc.dest_cnpj == "99888777000166"
    assert doc.emit_uf == "GO"
    assert doc.valor_pis == 24.75
    assert doc.valor_cofins == 114.0


def test_parse_nfe_modelo_65_nfce():
    doc = parse_nfe(_nfe_xml(modelo="65"))
    assert doc.tipo == "NFC-e"
    assert doc.modelo == "65"


def test_parse_nfe_xml_invalido():
    doc = parse_nfe(b"<?xml not valid")
    assert doc is not None
    assert doc.erros  # gera erro mas retorna shell


def test_parse_nfe_estrutura_irreconhecida():
    doc = parse_nfe(b"<?xml version=\"1.0\"?><root/>")
    assert doc is None


def test_parse_nfe_autorizada_por_default():
    doc = parse_nfe(_nfe_xml(numero="123"))
    assert doc.situacao == "AUTORIZADA"


def test_parse_nfe_cancelada_por_cstat():
    """NF-e com protocolo cStat=101 (cancelamento homologado) -> CANCELADA."""
    base = _nfe_xml(numero="500").decode()
    prot = "<protNFe><infProt><cStat>101</cStat></infProt></protNFe>"
    xml = base.replace("</nfeProc>", prot + "</nfeProc>").encode()
    doc = parse_nfe(xml)
    assert doc.situacao == "CANCELADA"


def test_parse_nfe_denegada_por_cstat():
    base = _nfe_xml(numero="501").decode()
    prot = "<protNFe><infProt><cStat>302</cStat></infProt></protNFe>"
    xml = base.replace("</nfeProc>", prot + "</nfeProc>").encode()
    assert parse_nfe(xml).situacao == "DENEGADA"


def test_lote_evento_de_cancelamento_marca_documento():
    """XML de evento (tpEvento 110111) marca o documento de mesma chave como CANCELADA."""
    chave = _chave_com_dv("3" * 43)
    nfe = _nfe_xml(numero="600", chave=chave)
    evento = (
        '<?xml version="1.0"?>'
        '<procEventoNFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        f"<evento><infEvento><tpEvento>110111</tpEvento><chNFe>{chave}</chNFe>"
        "</infEvento></evento></procEventoNFe>"
    ).encode()
    docs = parse_lote_xmls([("nfe.xml", nfe), ("evento.xml", evento)])
    assert len(docs) == 1  # o evento não vira documento
    assert docs[0].situacao == "CANCELADA"


# ────────────────────────────────────────────────────────────────────────
# parse_cte
# ────────────────────────────────────────────────────────────────────────


def test_parse_cte_basico():
    doc = parse_cte(_cte_xml(numero="999", valor="2500.00"))
    assert doc is not None
    assert doc.tipo == "CT-e"
    assert doc.modelo == "57"
    assert doc.numero == "999"
    assert doc.valor_total == 2500.0
    assert doc.emit_cnpj == "99888777000166"


def test_parse_cte_xml_invalido():
    doc = parse_cte(b"<not xml")
    assert doc is not None
    assert doc.erros


# ────────────────────────────────────────────────────────────────────────
# parse_nfse
# ────────────────────────────────────────────────────────────────────────


def test_parse_nfse_basico():
    doc = parse_nfse(_nfse_xml(numero="42", valor="800.00"))
    assert doc is not None
    assert doc.tipo == "NFS-e"
    assert doc.valor_total == 800.0
    assert doc.valor_iss == 40.0
    assert doc.emit_cnpj == "33333333000133"


def test_parse_nfse_invalido():
    assert parse_nfse(b"<lixo>") is None


# ────────────────────────────────────────────────────────────────────────
# detectar_e_parsear (autodetect)
# ────────────────────────────────────────────────────────────────────────


def test_autodetect_nfe():
    doc = detectar_e_parsear(_nfe_xml())
    assert doc.tipo == "NF-e"


def test_autodetect_cte():
    doc = detectar_e_parsear(_cte_xml())
    assert doc.tipo == "CT-e"


def test_autodetect_nfse():
    doc = detectar_e_parsear(_nfse_xml())
    assert doc.tipo == "NFS-e"


def test_autodetect_desconhecido():
    assert detectar_e_parsear(b"<?xml version=\"1.0\"?><foo/>") is None
    assert detectar_e_parsear(b"not xml") is None


# ────────────────────────────────────────────────────────────────────────
# parse_lote_xmls + extrair_xmls_zip
# ────────────────────────────────────────────────────────────────────────


def test_parse_lote_xmls_mixed():
    inputs = [
        ("nfe.xml", _nfe_xml(numero="1", valor="100")),
        ("cte.xml", _cte_xml(numero="2", valor="200")),
        ("nfse.xml", _nfse_xml(numero="3", valor="300")),
        ("lixo.xml", b"<not xml"),  # ignorado (sem chave)
    ]
    docs = parse_lote_xmls(inputs)
    # Inválidos sem chave são descartados
    tipos = sorted([d.tipo for d in docs])
    assert tipos == ["CT-e", "NF-e", "NFS-e"]


def test_extrair_xmls_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("nfe_001.xml", _nfe_xml(numero="1"))
        zf.writestr("nfe_002.xml", _nfe_xml(numero="2"))
        zf.writestr("readme.txt", b"ignored")
    xmls = extrair_xmls_zip(buf.getvalue())
    assert len(xmls) == 2
    assert all(name.endswith(".xml") for name, _ in xmls)


def test_extrair_xmls_zip_invalido():
    assert extrair_xmls_zip(b"not a zip") == []
