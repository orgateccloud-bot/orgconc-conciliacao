from pathlib import Path

src = Path("api/parsers/__init__.py").read_text(encoding="utf-8")
sections = {
    "ofx.py": ("# ── OFX", "# ── XML"),
    "xml_parser.py": ("# ── XML", "# ── PDF"),
    "pdf.py": ("# ── PDF", "# ── Router"),
    "router.py": ("# ── Router", "# ── Classificador"),
    "classifier.py": ("# ── Classificador", "# ── Detector"),
    "anomalies.py": ("# ── Detector", "# ── Estatisticas"),
    "stats.py": ("# ── Estatisticas", None),
}
header = 'from __future__ import annotations\n\n'
for fname, (start, end) in sections.items():
    i = src.index(start)
    j = len(src) if end is None else src.index(end)
    body = src[i:j].strip()
    lines = body.splitlines()
    if lines and lines[0].startswith("#"):
        body = "\n".join(lines[1:])
    Path(f"api/parsers/{fname}").write_text(header + body + "\n", encoding="utf-8")

init = '''"""Parsers de extratos bancarios — re-exporta API publica."""
from api.parsers.ofx import _parse_ofx
from api.parsers.xml_parser import _parse_xml
from api.parsers.pdf import _parse_pdf
from api.parsers.router import _parse_arquivo
from api.parsers.classifier import _classificar
from api.parsers.anomalies import _chave_transacao, _coletar_chaves_anomalas, _detectar_anomalias
from api.parsers.stats import _fmt_csv, _top_categorias_e_contrapartes

__all__ = [
    "_parse_arquivo", "_parse_ofx", "_parse_xml", "_parse_pdf",
    "_classificar", "_detectar_anomalias", "_chave_transacao", "_coletar_chaves_anomalas",
    "_top_categorias_e_contrapartes", "_fmt_csv",
]
'''
Path("api/parsers/__init__.py").write_text(init, encoding="utf-8")
print("split ok")
