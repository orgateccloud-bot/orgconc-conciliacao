"""Claude Vision: extrai transacoes de PDF mandando paginas como imagem.

Use para PDFs de scan / Print-to-PDF onde OCR Tesseract tem qualidade ruim,
ou para layouts atipicos que regex nao captura.

Fluxo:
1. PyMuPDF renderiza pagina como PNG (DPI configuravel).
2. Codifica base64.
3. Manda para Claude Vision com prompt structured-output.
4. Parser do JSON retornado.

Configuracao via env:
- ORGCONC_VISION_MAX_PAGES   : limite de paginas (default 20)
- ORGCONC_VISION_MODEL       : modelo Claude (default claude-sonnet-4-6)
- ORGCONC_VISION_DPI         : DPI render (default 150 — vision aceita ate 1568px)

Custo: cada imagem ~1500-2000 input tokens + output ~500-1500.
Sonnet 4.6: ~$0.005-0.015 por pagina. 20 paginas ~$0.10-0.30.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import time

from anthropic import Anthropic

log = logging.getLogger("orgconc.vision")


_VISION_MAX_PAGES = int(os.environ.get("ORGCONC_VISION_MAX_PAGES", "20"))
_VISION_MODEL = os.environ.get("ORGCONC_VISION_MODEL", "claude-sonnet-4-6")
_VISION_DPI = int(os.environ.get("ORGCONC_VISION_DPI", "150"))


_PROMPT_EXTRACAO = """Voce esta vendo uma pagina de extrato bancario brasileiro.

Extraia TODAS as transacoes desta pagina como JSON puro (sem markdown,
sem prosa, sem ```json). Formato exato:

{
  "transacoes": [
    {
      "data": "YYYY-MM-DD",
      "tipo": "CREDIT" ou "DEBIT",
      "valor": numero positivo para CREDIT, negativo para DEBIT (em reais),
      "memo": "descricao completa do lancamento",
      "nome": "contraparte (PIX/TED): nome ou vazio",
      "checknum": "numero do documento ou vazio"
    }
  ],
  "conta_detectada": "AG XXXX / CC YYYYYY" ou null se nao identificavel
}

REGRAS:
- Use somente dados visiveis. Nao invente.
- Se a pagina nao tem transacoes (capa, sumario, etc), retorne {"transacoes": [], "conta_detectada": null}.
- Datas no formato YYYY-MM-DD (converta DD/MM/YYYY).
- Valores em reais, sem R$, sem ponto de milhar, com ponto decimal: "1234.56" → 1234.56.
- Saidas/debitos: valor NEGATIVO. Entradas/creditos: POSITIVO.
- "memo" maximo 200 caracteres."""


def disponivel() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _renderizar_pagina_b64(doc, idx: int) -> str:
    """Renderiza pagina como PNG e retorna base64."""
    import pymupdf
    zoom = _VISION_DPI / 72.0
    page = doc[idx]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return base64.standard_b64encode(pix.tobytes("png")).decode("ascii")


def _parsear_resposta_json(texto: str) -> dict:
    """Extrai JSON da resposta Claude, tolerante a markdown ```json...```."""
    texto = texto.strip()
    if texto.startswith("```"):
        m = re.search(r"```(?:json)?\s*\n(.*?)\n```", texto, re.DOTALL)
        if m:
            texto = m.group(1)
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        # Tentativa: pegar o primeiro {...} balanceado
        m = re.search(r"\{.*\}", texto, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"transacoes": [], "conta_detectada": None}


def extrair_via_vision(
    pdf_bytes: bytes,
    filename: str,
    api_key: str | None = None,
) -> list[dict]:
    """Manda PDF (paginas) para Claude Vision e parseia transacoes.

    Retorna lista normalizada (mesmo schema do parser regex).
    """
    api_key = (api_key or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
    if not api_key:
        log.warning("Vision: ANTHROPIC_API_KEY ausente — pulando")
        return []

    try:
        import pymupdf
    except ImportError:
        log.warning("Vision: PyMuPDF nao instalado")
        return []

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        log.exception("Vision: PyMuPDF nao conseguiu abrir %s", filename)
        return []

    total = len(doc)
    paginas_a_processar = min(total, _VISION_MAX_PAGES)
    if total > _VISION_MAX_PAGES:
        log.warning(
            "Vision %s: %d paginas; processando primeiras %d (limite ORGCONC_VISION_MAX_PAGES)",
            filename, total, _VISION_MAX_PAGES,
        )

    log.info(
        "Vision %s: iniciando %d paginas (modelo=%s, dpi=%d)",
        filename, paginas_a_processar, _VISION_MODEL, _VISION_DPI,
    )

    client = Anthropic(api_key=api_key)
    transacoes: list[dict] = []
    conta_detectada: str | None = None
    vistos: set[tuple[str, float, str]] = set()
    t0 = time.perf_counter()
    total_input = 0
    total_output = 0

    try:
        for idx in range(paginas_a_processar):
            try:
                img_b64 = _renderizar_pagina_b64(doc, idx)
            except Exception:
                log.exception("Vision: render falhou pag %d de %s", idx, filename)
                continue

            try:
                resp = client.messages.create(
                    model=_VISION_MODEL,
                    max_tokens=4000,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": img_b64,
                                },
                            },
                            {"type": "text", "text": _PROMPT_EXTRACAO},
                        ],
                    }],
                )
                total_input += resp.usage.input_tokens
                total_output += resp.usage.output_tokens
                texto = "\n".join(b.text for b in resp.content if b.type == "text")
                data = _parsear_resposta_json(texto)
            except Exception:
                log.exception("Vision: API falhou pag %d de %s", idx, filename)
                continue

            if conta_detectada is None and data.get("conta_detectada"):
                conta_detectada = str(data["conta_detectada"])

            for t in data.get("transacoes", []):
                try:
                    valor = float(t["valor"])
                    data_str = str(t["data"])
                    memo = str(t.get("memo", ""))[:200]
                    chave = (data_str, round(valor, 2), memo[:40])
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    transacoes.append({
                        "conta": conta_detectada or f"VISION ({filename})",
                        "data": data_str,
                        "tipo": str(t.get("tipo", "CREDIT" if valor > 0 else "DEBIT")),
                        "valor": valor,
                        "memo": memo,
                        "nome": str(t.get("nome", ""))[:120],
                        "checknum": str(t.get("checknum", ""))[:30],
                    })
                except (KeyError, ValueError, TypeError):
                    log.debug("Vision: transacao mal-formada ignorada em pag %d", idx)
                    continue

            if (idx + 1) % 5 == 0:
                elapsed = time.perf_counter() - t0
                log.info(
                    "Vision %s: %d/%d paginas — %d transacoes acumuladas (%.1fs, tokens in=%d out=%d)",
                    filename, idx + 1, paginas_a_processar, len(transacoes),
                    elapsed, total_input, total_output,
                )
    finally:
        doc.close()

    elapsed = time.perf_counter() - t0
    # Atualiza conta detectada nos registros antigos se necessario
    if conta_detectada:
        for t in transacoes:
            if t["conta"].startswith("VISION "):
                t["conta"] = conta_detectada

    log.info(
        "Vision %s: concluido em %.1fs — %d transacoes / %d paginas (in=%d out=%d tokens)",
        filename, elapsed, len(transacoes), paginas_a_processar,
        total_input, total_output,
    )
    return transacoes
