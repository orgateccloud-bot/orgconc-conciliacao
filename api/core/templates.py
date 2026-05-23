"""Jinja2 e assets estaticos para relatorios."""
from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from api.core.config import STATIC_DIR

_templates_dir = Path(__file__).resolve().parent.parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=select_autoescape(["html"]),
)

_LOGO_PATH = STATIC_DIR / "logo.png"
LOGO_B64 = ""
LOGO_DATA_URI = ""
if _LOGO_PATH.exists():
    LOGO_B64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()
    LOGO_DATA_URI = f"data:image/png;base64,{LOGO_B64}"
