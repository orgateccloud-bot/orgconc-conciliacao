"""Parsers de extratos bancarios + classificador contabil + detector de anomalias.

Este modulo agrega o contrato publico mantendo a compat com `api.main` e
demais consumidores. As implementacoes corrigidas vivem nos modulos
dedicados (ofx, pdf, xml_parser, anomalies, constants, classifier, stats).

Funcoes publicas (mantem prefixo _ por compat):
- _parse_arquivo(content, filename) -> list[dict]    | router por magic bytes
- _detectar_tipo(content, filename) -> str           | detecta tipo via magic bytes
- _parse_ofx(text) -> list[dict]                      | parser OFX SGML (modulo ofx)
- _parse_xml(text, filename) -> list[dict]            | parser CAMT.053 / OFX-XML (modulo xml_parser)
- _parse_pdf(content, filename) -> list[dict]         | parser PDF bancario (modulo pdf)
- _classificar(memo, nome) -> str                     | classificador contabil (modulo classifier)
- _detectar_anomalias(extratos) -> list[dict]         | detector multi-severidade (modulo anomalies)
- _chave_transacao(conta, t) -> tuple                 | chave unica de persistencia (modulo anomalies)
- _coletar_chaves_anomalas(extratos) -> set           | (modulo anomalies)
- _top_categorias_e_contrapartes(extratos) -> dict    | estatisticas (modulo stats)
- _fmt_csv(transacoes) -> str                         | formata CSV para prompt LLM (modulo stats)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

# Imports das implementacoes dedicadas (corrigidas) — fonte unica de verdade
from api.parsers.anomalies import (
    _chave_transacao,
    _coletar_chaves_anomalas,
    _detectar_anomalias,
)
from api.parsers.classifier import _classificar
from api.parsers.constants import (
    LIMITE_VALOR_ALTO,
    LIMITE_VALOR_CRITICO,
    PALAVRAS_ESTORNO,
    _KEYWORDS_TRANSF,
)
from api.parsers.ofx import _parse_ofx
from api.parsers.pdf import _parse_pdf
from api.parsers.stats import _fmt_csv, _top_categorias_e_contrapartes
from api.parsers.xml_parser import _parse_xml


# ── Router por extensao + magic bytes ───────────────────────────────────────

# Assinaturas de magic bytes para validar tipo real do arquivo
_MAGIC_BYTES: list[tuple[bytes, str]] = [
    (b"%PDF", ".pdf"),
    (b"<?xml", ".xml"),
    (b"<OFX", ".ofx"),
    (b"OFXHEADER", ".ofx"),
]


def _detectar_tipo(content: bytes, filename: str) -> str:
    """Retorna extensao baseada em magic bytes (fallback: extensao do filename)."""
    head = content[:16].lstrip()
    for magic, ext in _MAGIC_BYTES:
        if head.startswith(magic):
            return ext
    return Path(filename).suffix.lower()


def _parse_arquivo(content: bytes, filename: str) -> list[dict]:
    """Detecta tipo do arquivo por magic bytes e roteia para o parser correto."""
    ext = _detectar_tipo(content, filename)
    if ext == ".ofx":
        return _parse_ofx(content.decode("latin-1", errors="ignore"))
    if ext == ".pdf":
        return _parse_pdf(content, filename)
    if ext == ".xml":
        return _parse_xml(content.decode("utf-8", errors="ignore"), filename)
    raise HTTPException(
        status_code=400,
        detail=f"Extensao nao suportada: {ext}. Use .ofx, .pdf ou .xml",
    )


__all__ = [
    "_parse_arquivo",
    "_detectar_tipo",
    "_parse_ofx",
    "_parse_pdf",
    "_parse_xml",
    "_classificar",
    "_detectar_anomalias",
    "_chave_transacao",
    "_coletar_chaves_anomalas",
    "_top_categorias_e_contrapartes",
    "_fmt_csv",
    "LIMITE_VALOR_ALTO",
    "LIMITE_VALOR_CRITICO",
    "PALAVRAS_ESTORNO",
    "_KEYWORDS_TRANSF",
]
