"""Fallback OCR para PDFs sem texto extraivel.

Renderiza cada pagina como PNG (PyMuPDF), roda Tesseract com PSM=6
(single uniform block — preserva linhas) e reaplica regex de
`api/parsers/pdf.py::aplicar_regex_em_texto`.

Heuristica para extratos brasileiros: bancos como Sicoob/Bradesco omitem
ano e mostram apenas `dd/mm` por linha (ano fica no header da pagina).
Antes de aplicar regex, detectamos o ano em `Periodo: XX/XX/YYYY` e
injetamos nas datas curtas.

Configuracao via env:
- ORGCONC_OCR_ENABLED       : default true
- ORGCONC_OCR_MAX_PAGES     : default 50
- ORGCONC_OCR_LANG          : default "por+eng"
- ORGCONC_OCR_DPI           : default 200
- ORGCONC_OCR_PSM           : default 6 (single uniform block)
- ORGCONC_TESSERACT_CMD     : caminho do binario
"""
from __future__ import annotations

import io
import logging
import os
import re
import time
from typing import Iterable

log = logging.getLogger("orgconc.parsers.ocr")


_OCR_MAX_PAGES = int(os.environ.get("ORGCONC_OCR_MAX_PAGES", "50"))
_OCR_LANG = os.environ.get("ORGCONC_OCR_LANG", "por+eng")
_OCR_DPI = int(os.environ.get("ORGCONC_OCR_DPI", "200"))
_OCR_PSM = int(os.environ.get("ORGCONC_OCR_PSM", "6"))

# Casa "Periodo: 01/04/2026 - 30/04/2026", "Mes Referencia: 04/2026", etc.
_RX_ANO_REF = re.compile(
    r"(?:per[ií]odo|m[êe]s\s*refer[êe]ncia|extrato|mes)\s*[:\s]\s*"
    r"\d{0,2}[/-]?\d{0,2}[/-]?(20\d{2})",
    re.IGNORECASE,
)
# Casa "30/04 " no comeco de uma linha (data BR curta)
_RX_DATA_CURTA = re.compile(r"(?m)(?<=\b)(\d{2})/(\d{2})(?=\s+)")


def _configurar_tesseract() -> bool:
    """Configura caminho do binario Tesseract se necessario."""
    import pytesseract

    cmd = os.environ.get("ORGCONC_TESSERACT_CMD", "").strip()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        return True

    # Tentativa Windows default
    win_default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.name == "nt" and os.path.exists(win_default):
        pytesseract.pytesseract.tesseract_cmd = win_default
        return True

    # Assume PATH (Linux/Mac)
    return True


def _detectar_ano(texto: str) -> str | None:
    """Procura ano no header da pagina."""
    m = _RX_ANO_REF.search(texto)
    return m.group(1) if m else None


def _expandir_datas(texto: str, ano: str) -> str:
    """Converte `dd/mm ` em `dd/mm/AAAA ` no texto OCR."""
    return _RX_DATA_CURTA.sub(rf"\1/\2/{ano}", texto)


def extrair_via_ocr(
    pdf_bytes: bytes,
    filename: str,
    paginas_idx: Iterable[int],
    conta: str,
) -> list[dict]:
    """OCR + regex sobre paginas indicadas. Retorna lista de transacoes."""
    if not _configurar_tesseract():
        log.warning("Tesseract nao configurado — OCR desativado")
        return []

    try:
        import pymupdf  # PyMuPDF
        import pytesseract
        from PIL import Image
    except ImportError as e:
        log.warning("Deps OCR faltando (%s) — pulando OCR", e.name)
        return []

    # Lazy import para evitar ciclo
    from api.parsers.pdf import aplicar_regex_em_texto

    paginas = list(paginas_idx)
    if not paginas:
        return []

    if len(paginas) > _OCR_MAX_PAGES:
        log.warning(
            "PDF %s tem %d paginas sem texto; OCR limitado a %d primeiras",
            filename, len(paginas), _OCR_MAX_PAGES,
        )
        paginas = paginas[:_OCR_MAX_PAGES]

    log.info(
        "OCR %s: iniciando %d paginas (lang=%s, dpi=%d, psm=%d)",
        filename, len(paginas), _OCR_LANG, _OCR_DPI, _OCR_PSM,
    )

    transacoes: list[dict] = []
    vistos: set[tuple[str, float, str]] = set()
    zoom = _OCR_DPI / 72.0
    config_tess = f"--psm {_OCR_PSM}"
    ano_persistente: str | None = None

    t0 = time.perf_counter()
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        log.exception("PyMuPDF nao conseguiu abrir %s", filename)
        return []

    try:
        for n_processadas, idx in enumerate(paginas, 1):
            if idx >= len(doc):
                continue
            try:
                page = doc[idx]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                texto = pytesseract.image_to_string(img, lang=_OCR_LANG, config=config_tess)

                # Detecta ano no header dessa pagina (e cacheia para as proximas)
                ano = _detectar_ano(texto) or ano_persistente
                if ano:
                    ano_persistente = ano
                    texto_expandido = _expandir_datas(texto, ano)
                else:
                    texto_expandido = texto

                novas = aplicar_regex_em_texto(texto_expandido, conta, vistos)
                if novas:
                    log.debug(
                        "OCR %s pag %d: %d transacoes (ano=%s)",
                        filename, idx, len(novas), ano,
                    )
                    transacoes.extend(novas)
            except Exception:
                log.exception("OCR falhou na pagina %d de %s", idx, filename)
                continue

            if n_processadas % 10 == 0:
                elapsed = time.perf_counter() - t0
                log.info(
                    "OCR %s: %d/%d paginas processadas (%.1fs, %d transacoes ate agora)",
                    filename, n_processadas, len(paginas), elapsed, len(transacoes),
                )
    finally:
        doc.close()

    elapsed = time.perf_counter() - t0
    log.info(
        "OCR %s: concluido em %.1fs — %d transacoes de %d paginas",
        filename, elapsed, len(transacoes), len(paginas),
    )
    return transacoes
