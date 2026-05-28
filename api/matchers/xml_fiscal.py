"""Parser unificado de documentos fiscais XML — NF-e (mod 55) + CT-e (mod 57) + NFS-e.

Sprint 1 do Plano de Integração Fiscal: este módulo extrai metadados estruturados
de XMLs fiscais brasileiros em formato uniforme para persistência e cruzamento.

Diferenças em relação a `api/matchers/nfe.py`:
- Não tenta casar contra OFX (esse é o papel de `cruzamento_fiscal.py`).
- Suporta NF-e (mod 55), CT-e (mod 57) e NFS-e (estrutura genérica).
- Retorna `DocumentoFiscalLido` com campos comuns a todos os modelos.
- Detecta automaticamente o tipo pelo elemento raiz e pelo `mod`.
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from typing import Iterable, Optional


@dataclass
class DocumentoFiscalLido:
    """Documento fiscal parseado a partir de XML (NF-e/CT-e/NFS-e)."""

    tipo: str  # "NF-e" | "CT-e" | "NFS-e"
    modelo: str  # "55" | "57" | "65" | "00" (NFS-e)
    chave: str  # 44 dígitos
    numero: str
    serie: str
    data_emissao: str  # AAAA-MM-DD
    emit_cnpj: str
    emit_nome: str
    emit_uf: str
    dest_cnpj: str
    dest_nome: str
    valor_total: float
    valor_icms: float = 0.0
    valor_pis: float = 0.0
    valor_cofins: float = 0.0
    valor_iss: float = 0.0
    cfop: str = ""
    natureza_operacao: str = ""
    municipio_emit: str = ""
    erros: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _filho(elem, nome: str):
    if elem is None:
        return None
    for f in elem:
        if _local(f.tag) == nome:
            return f
    return None


def _texto(elem, *caminho: str) -> str:
    cur = elem
    for nome in caminho:
        cur = _filho(cur, nome)
        if cur is None:
            return ""
    return cur.text.strip() if cur is not None and cur.text else ""


def _to_float(s: str) -> float:
    try:
        return float(s) if s else 0.0
    except (ValueError, TypeError):
        return 0.0


def _achar_inf(root, *nomes: str):
    """Encontra o primeiro descendente cujo tag local está em `nomes`."""
    for elem in root.iter():
        if _local(elem.tag) in nomes:
            return elem
    return None


def parse_nfe(conteudo: bytes) -> Optional[DocumentoFiscalLido]:
    """Parser NF-e (modelo 55) ou NFC-e (modelo 65)."""
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError as e:
        return DocumentoFiscalLido(
            tipo="NF-e", modelo="", chave="", numero="", serie="",
            data_emissao="", emit_cnpj="", emit_nome="", emit_uf="",
            dest_cnpj="", dest_nome="", valor_total=0.0,
            erros=[f"XML inválido: {e}"],
        )
    inf = _achar_inf(root, "infNFe")
    if inf is None:
        return None

    ide = _filho(inf, "ide")
    emit = _filho(inf, "emit")
    dest = _filho(inf, "dest")
    total = _filho(inf, "total")
    icms_tot = _filho(total, "ICMSTot") if total is not None else None

    modelo = _texto(ide, "mod") or "55"
    tipo = "NFC-e" if modelo == "65" else "NF-e"

    chave = (inf.get("Id") or "").lstrip("NFe").lstrip("NFCe")
    data = (_texto(ide, "dhEmi") or _texto(ide, "dEmi"))[:10]

    emit_uf = _texto(emit, "enderEmit", "UF")
    mun_emit = _texto(emit, "enderEmit", "xMun")

    return DocumentoFiscalLido(
        tipo=tipo,
        modelo=modelo,
        chave=chave,
        numero=_texto(ide, "nNF"),
        serie=_texto(ide, "serie"),
        data_emissao=data,
        emit_cnpj=_texto(emit, "CNPJ") or _texto(emit, "CPF"),
        emit_nome=_texto(emit, "xNome"),
        emit_uf=emit_uf,
        dest_cnpj=_texto(dest, "CNPJ") or _texto(dest, "CPF") if dest is not None else "",
        dest_nome=_texto(dest, "xNome") if dest is not None else "",
        valor_total=_to_float(_texto(icms_tot, "vNF") if icms_tot is not None else ""),
        valor_icms=_to_float(_texto(icms_tot, "vICMS") if icms_tot is not None else ""),
        valor_pis=_to_float(_texto(icms_tot, "vPIS") if icms_tot is not None else ""),
        valor_cofins=_to_float(_texto(icms_tot, "vCOFINS") if icms_tot is not None else ""),
        natureza_operacao=_texto(ide, "natOp"),
        municipio_emit=mun_emit,
    )


def parse_cte(conteudo: bytes) -> Optional[DocumentoFiscalLido]:
    """Parser CT-e (modelo 57) ou CT-e OS (modelo 67)."""
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError as e:
        return DocumentoFiscalLido(
            tipo="CT-e", modelo="", chave="", numero="", serie="",
            data_emissao="", emit_cnpj="", emit_nome="", emit_uf="",
            dest_cnpj="", dest_nome="", valor_total=0.0,
            erros=[f"XML inválido: {e}"],
        )
    inf = _achar_inf(root, "infCte", "infCTe")
    if inf is None:
        return None

    ide = _filho(inf, "ide")
    emit = _filho(inf, "emit")
    rem = _filho(inf, "rem")
    dest = _filho(inf, "dest")
    vprest = _filho(inf, "vPrest")
    imposto = _filho(inf, "imp")
    icms = _filho(imposto, "ICMS") if imposto is not None else None

    chave = (inf.get("Id") or "").lstrip("CTe")
    data = (_texto(ide, "dhEmi") or _texto(ide, "dEmi"))[:10]
    modelo = _texto(ide, "mod") or "57"

    # CT-e usa "rem" para remetente e "dest" para destinatário; o emitente é a transportadora.
    # Para fins de auditoria, "emit" = quem prestou o serviço (transportadora).
    return DocumentoFiscalLido(
        tipo="CT-e",
        modelo=modelo,
        chave=chave,
        numero=_texto(ide, "nCT"),
        serie=_texto(ide, "serie"),
        data_emissao=data,
        emit_cnpj=_texto(emit, "CNPJ") if emit is not None else "",
        emit_nome=_texto(emit, "xNome") if emit is not None else "",
        emit_uf=_texto(emit, "enderEmit", "UF") if emit is not None else _texto(ide, "UFIni"),
        dest_cnpj=_texto(dest, "CNPJ") if dest is not None else (_texto(rem, "CNPJ") if rem is not None else ""),
        dest_nome=_texto(dest, "xNome") if dest is not None else (_texto(rem, "xNome") if rem is not None else ""),
        valor_total=_to_float(_texto(vprest, "vTPrest") if vprest is not None else ""),
        valor_icms=_to_float(_texto(_filho(icms, "ICMS00") or _filho(icms, "ICMS20") or _filho(icms, "ICMS60") or icms, "vICMS") if icms is not None else ""),
        natureza_operacao=_texto(ide, "natOp"),
    )


def parse_nfse(conteudo: bytes) -> Optional[DocumentoFiscalLido]:
    """Parser NFS-e (Nota Fiscal de Serviços Eletrônica - municipal).

    Schema genérico ABRASF; municípios podem ter variações.
    """
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError:
        return None

    inf = _achar_inf(root, "InfNfse", "InfDeclaracaoPrestacaoServico")
    if inf is None:
        return None

    numero = _texto(inf, "Numero")
    chave = numero  # NFS-e não tem chave de 44 dígitos universal
    data = _texto(inf, "DataEmissao")[:10] or _texto(inf, "Competencia")[:10]

    prest = _filho(inf, "PrestadorServico") or _filho(inf, "Prestador")
    tom = _filho(inf, "TomadorServico") or _filho(inf, "Tomador")
    serv = _filho(inf, "Servico")
    valores = _filho(serv, "Valores") if serv is not None else None
    ident_prest = _filho(prest, "IdentificacaoPrestador") if prest is not None else None
    ident_tom = _filho(tom, "IdentificacaoTomador") if tom is not None else None
    cpf_cnpj_prest = _filho(ident_prest, "CpfCnpj") if ident_prest is not None else None
    cpf_cnpj_tom = _filho(ident_tom, "CpfCnpj") if ident_tom is not None else None

    return DocumentoFiscalLido(
        tipo="NFS-e",
        modelo="00",
        chave=chave or "",
        numero=numero,
        serie="",
        data_emissao=data,
        emit_cnpj=_texto(cpf_cnpj_prest, "Cnpj") or _texto(cpf_cnpj_prest, "Cpf") if cpf_cnpj_prest is not None else "",
        emit_nome=_texto(prest, "RazaoSocial") if prest is not None else "",
        emit_uf="",
        dest_cnpj=_texto(cpf_cnpj_tom, "Cnpj") or _texto(cpf_cnpj_tom, "Cpf") if cpf_cnpj_tom is not None else "",
        dest_nome=_texto(tom, "RazaoSocial") if tom is not None else "",
        valor_total=_to_float(_texto(valores, "ValorServicos") if valores is not None else ""),
        valor_iss=_to_float(_texto(valores, "ValorIss") if valores is not None else ""),
        valor_pis=_to_float(_texto(valores, "ValorPis") if valores is not None else ""),
        valor_cofins=_to_float(_texto(valores, "ValorCofins") if valores is not None else ""),
    )


def detectar_e_parsear(conteudo: bytes) -> Optional[DocumentoFiscalLido]:
    """Detecta automaticamente o tipo do documento e chama o parser apropriado."""
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError:
        return None
    for elem in root.iter():
        local = _local(elem.tag)
        if local == "infNFe":
            return parse_nfe(conteudo)
        if local in ("infCte", "infCTe"):
            return parse_cte(conteudo)
        if local in ("InfNfse", "InfDeclaracaoPrestacaoServico"):
            return parse_nfse(conteudo)
    return None


def parse_lote_xmls(xmls: Iterable[tuple[str, bytes]]) -> list[DocumentoFiscalLido]:
    """Parseia lote de XMLs e retorna lista de DocumentoFiscalLido (descarta inválidos)."""
    docs: list[DocumentoFiscalLido] = []
    for _filename, conteudo in xmls:
        doc = detectar_e_parsear(conteudo)
        if doc is not None and doc.chave:
            docs.append(doc)
    return docs


def extrair_xmls_zip(zip_bytes: bytes) -> list[tuple[str, bytes]]:
    """Extrai todos os XMLs de um ZIP em memória."""
    xmls: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for member in zf.namelist():
                if member.lower().endswith(".xml"):
                    with zf.open(member) as fh:
                        xmls.append((member, fh.read()))
    except zipfile.BadZipFile:
        pass
    return xmls
