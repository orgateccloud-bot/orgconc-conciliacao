"""Jinja2 e assets estaticos para relatorios."""
from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_templates_dir = Path(__file__).resolve().parent.parent / "templates"
# Falso-positivo: regra e' especifica de Flask (render_template); aqui e' FastAPI
# com autoescape ativo para .html — unicos templates do diretorio.
# nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
jinja_env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=select_autoescape(["html"]),
)

_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
LOGO_B64 = ""
LOGO_DATA_URI = ""
if _LOGO_PATH.exists():
    LOGO_B64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()
    LOGO_DATA_URI = f"data:image/png;base64,{LOGO_B64}"
