"""Helpers para inserir o logo ORGATEC nos relatorios (XLSX/HTML/PDF)."""
from __future__ import annotations

import base64
from pathlib import Path

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "orgatec_logo.png"


def logo_existe() -> bool:
    return LOGO_PATH.exists()


def logo_data_uri() -> str:
    """Retorna o logo como data:URI base64 para uso em HTML/CSS."""
    if not LOGO_PATH.exists():
        return ""
    b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def inserir_logo_xlsx(ws, anchor: str = "A1", largura_px: int = 70, altura_px: int = 70):
    """Insere o logo numa celula do XLSX com redimensionamento."""
    if not LOGO_PATH.exists():
        return False
    try:
        from openpyxl.drawing.image import Image as XLImage
        img = XLImage(str(LOGO_PATH))
        img.width = largura_px
        img.height = altura_px
        img.anchor = anchor
        ws.add_image(img)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  AVISO: falha ao inserir logo no XLSX: {exc}")
        return False


def html_logo_inline() -> str:
    """Retorna tag <img> com logo inline para uso no cabecalho HTML."""
    uri = logo_data_uri()
    if not uri:
        return ""
    return (
        f'<img src="{uri}" alt="ORGATEC" '
        f'style="width:64px;height:64px;vertical-align:middle;'
        f'margin-right:18px;filter:drop-shadow(0 4px 12px rgba(77,124,255,0.45));"/>'
    )
