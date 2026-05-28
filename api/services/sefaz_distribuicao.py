"""Stub de integração com SEFAZ Distribuição DFe (NSU).

Sprint 4 do Plano de Integração Fiscal — STUB DE ROADMAP.

A integração completa requer:
1. Certificado digital A1 ou A3 do cliente
2. Endpoints SOAP da SEFAZ (UF do destinatário)
3. Schemas WSDL (distDFeInt, retDistDFeInt)
4. Assinatura digital XMLDSig
5. Persistência do último NSU (Número Sequencial Único) processado

Este módulo expõe a interface esperada (`baixar_nfes_pendentes`) mas retorna
sempre erro NOT_IMPLEMENTED. Permite o resto do sistema referenciar a API
sem quebrar.

Quando integrar de verdade, substituir o conteúdo de `_chamar_sefaz_real`
por chamadas SOAP via zeep/lxml + signxml.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("orgconc.sefaz")


@dataclass
class DocumentoSefaz:
    """Documento retornado pela SEFAZ Distribuição DFe."""

    chave: str
    nsu: str
    schema: str  # resNFe / procNFe / procEventoNFe
    xml_bytes: bytes


@dataclass
class ResultadoDistribuicao:
    nsu_inicial: str
    nsu_final: str
    documentos: list[DocumentoSefaz]
    erro: Optional[str] = None


async def baixar_nfes_pendentes(
    cnpj_destinatario: str,
    uf: str,
    nsu_ultimo: str = "0",
    cert_path: Optional[str] = None,
    cert_password: Optional[str] = None,
) -> ResultadoDistribuicao:
    """STUB — em produção fará chamada SOAP à SEFAZ.

    Retorna ResultadoDistribuicao vazio com erro NOT_IMPLEMENTED.
    """
    log.info(
        "sefaz.distribuicao: STUB invocado cnpj=%s uf=%s nsu=%s",
        cnpj_destinatario, uf, nsu_ultimo,
    )
    return ResultadoDistribuicao(
        nsu_inicial=nsu_ultimo,
        nsu_final=nsu_ultimo,
        documentos=[],
        erro="NOT_IMPLEMENTED: integração SEFAZ requer certificado digital + WSDL",
    )


async def consultar_status_servico(uf: str) -> dict:
    """STUB — consulta status do serviço SEFAZ por UF."""
    return {
        "uf": uf,
        "status": "STUB",
        "mensagem": "Integração SEFAZ pendente — usar SEFAZ-GO via portal manualmente",
    }
