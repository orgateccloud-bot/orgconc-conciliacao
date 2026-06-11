"""Utilitários centralizados de formatação e CSS para os relatórios OrgConc.

Todas as funções de formatação de números/datas pt-BR e a geração de CSS com
fontes embarcadas (`@font-face` via data-URI) ficam aqui — único ponto de
verdade para XLSX, HTML e PDF.

Fontes (api/assets/fonts/*.woff2) são carregadas e codificadas em base64 UMA
vez no import; o custo de I/O não se repete por chamada.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
_ASSETS = Path(__file__).resolve().parents[1] / "assets"        # api/assets/
_FONTS_DIR = _ASSETS / "fonts"                                   # api/assets/fonts/
_TOKENS_PATH = Path(__file__).resolve().parents[2] / "shared" / "report-tokens.json"  # shared/

# ── Tokens ───────────────────────────────────────────────────────────────
def _load_tokens() -> dict:
    try:
        return json.loads(_TOKENS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

TOKENS: dict = _load_tokens()


# ── Formatação pt-BR ─────────────────────────────────────────────────────

def format_brl(valor: float | int | None, *, sinal: bool = False) -> str:
    """Valor monetário pt-BR: 1.234.567,89  (sem prefixo R$).
    Com sinal=True: +1.234,56 / -1.234,56.
    """
    if valor is None:
        return "—"
    v = float(valor)
    s = f"{abs(v):,.2f}"                              # "1,234,567.89"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # "1.234.567,89"
    if sinal:
        return ("+" if v >= 0 else "-") + s
    return s


def format_num(valor: float | int | None, decimais: int = 0) -> str:
    """Número inteiro ou decimal pt-BR: 1.234 ou 1.234,56."""
    if valor is None:
        return "—"
    v = float(valor)
    if decimais == 0:
        s = f"{abs(v):,.0f}".replace(",", ".")
    else:
        s = f"{abs(v):,.{decimais}f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + s


def format_pct(valor: float | None, decimais: int = 1) -> str:
    """Percentual pt-BR: 12,3%."""
    if valor is None:
        return "—"
    return format_num(valor * 100, decimais=decimais) + "%"


# ── CSS de fontes embarcadas ─────────────────────────────────────────────

_FONT_FACES: str | None = None  # cache do CSS, gerado uma vez


def _b64_woff2(name: str) -> str:
    """Lê o arquivo WOFF2 e retorna base64 (string vazia se ausente)."""
    p = _FONTS_DIR / name
    if not p.exists():
        return ""
    return base64.b64encode(p.read_bytes()).decode("ascii")


def font_faces_css() -> str:
    """Retorna CSS com @font-face data-URI para as 3 famílias da marca.

    Gerado uma vez e cacheado — seguro para uso em múltiplas requisições.
    Fallback gracioso se os arquivos de fonte estiverem ausentes (usa fontes
    de sistema, mas o layout não quebra).
    """
    global _FONT_FACES
    if _FONT_FACES is not None:
        return _FONT_FACES

    def face(family: str, weight: int, style: str, fname: str) -> str:
        data = _b64_woff2(fname)
        if not data:
            return ""
        return (
            f"@font-face {{\n"
            f"  font-family: '{family}';\n"
            f"  font-weight: {weight};\n"
            f"  font-style: {style};\n"
            f"  font-display: swap;\n"
            f"  src: url('data:font/woff2;base64,{data}') format('woff2');\n"
            f"}}\n"
        )

    parts = [
        face("Manrope", 400, "normal", "manrope-latin-400-normal.woff2"),
        face("Manrope", 600, "normal", "manrope-latin-600-normal.woff2"),
        face("Manrope", 700, "normal", "manrope-latin-700-normal.woff2"),
        face("Instrument Serif", 400, "normal", "instrument-serif-latin-400-normal.woff2"),
        face("Instrument Serif", 400, "italic", "instrument-serif-latin-400-italic.woff2"),
        face("JetBrains Mono", 400, "normal", "jetbrains-mono-latin-400-normal.woff2"),
        face("JetBrains Mono", 500, "normal", "jetbrains-mono-latin-500-normal.woff2"),
    ]
    _FONT_FACES = "\n".join(p for p in parts if p)
    return _FONT_FACES


# ── Variáveis CSS derivadas dos tokens ───────────────────────────────────

def tokens_css_vars() -> str:
    """Retorna declarações CSS :root com as variáveis dos tokens."""
    p = TOKENS.get("paleta", {})
    f = TOKENS.get("financeiro", {})
    s = TOKENS.get("severidade", {})
    lines = [":root {"]
    for k, v in p.items():
        lines.append(f"  --rpt-{k}: {v};")
    lines.append(f"  --rpt-credito: {f.get('credito', '#16A34A')};")
    lines.append(f"  --rpt-debito:  {f.get('debito',  '#DC2626')};")
    for nome, vals in s.items():
        n = nome.lower()
        lines.append(f"  --rpt-sev-{n}-bg:     {vals['bg']};")
        lines.append(f"  --rpt-sev-{n}-texto:  {vals['texto']};")
        lines.append(f"  --rpt-sev-{n}-solido: {vals['solido']};")
    lines.append("}")
    return "\n".join(lines)
