from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from api.parsers.markdown import _parse_md
from api.parsers.ofx import _parse_ofx
from api.parsers.pdf import _parse_pdf
from api.parsers.xml_parser import _parse_xml


def _parse_arquivo(content: bytes, filename: str) -> list[dict]:
    """Detecta tipo do arquivo e roteia para o parser correto."""
    ext = Path(filename).suffix.lower()
    if ext == ".ofx":
        return _parse_ofx(content.decode("latin-1", errors="ignore"))
    if ext == ".pdf":
        return _parse_pdf(content, filename)
    if ext == ".xml":
        return _parse_xml(content.decode("utf-8", errors="ignore"), filename)
    if ext in (".md", ".markdown", ".txt"):
        return _parse_md(content.decode("utf-8", errors="ignore"), filename)
    raise HTTPException(
        status_code=400,
        detail=f"Extensao nao suportada: {ext}. Use .ofx, .pdf, .xml, .md ou .txt",
    )
