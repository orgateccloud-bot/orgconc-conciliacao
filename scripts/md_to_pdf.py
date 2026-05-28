"""Converte o RELATORIO_CONSOLIDADO.md em PDF via WeasyPrint."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import markdown as md_lib


MD_PATH = Path(r"C:\Users\Veloso\Downloads\RELATORIO_CONSOLIDADO.md")
PDF_PATH = Path(r"C:\Users\Veloso\Downloads\RELATORIO_CONSOLIDADO_v2.pdf")
HTML_FALLBACK = Path(r"C:\Users\Veloso\Downloads\RELATORIO_CONSOLIDADO.html")

CSS = """
@page {
  size: A4;
  margin: 18mm 16mm 18mm 16mm;
  @bottom-right {
    content: "Pagina " counter(page) " de " counter(pages);
    font-size: 9px;
    color: #6B7280;
    font-family: 'DejaVu Sans', Arial, sans-serif;
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'DejaVu Sans', Arial, Helvetica, sans-serif;
  font-size: 10pt;
  color: #1a202c;
  line-height: 1.55;
}
.hd {
  background: linear-gradient(135deg, #0F172A 0%, #0B1B3D 45%, #0052FF 100%);
  color: #fff;
  padding: 22px 28px;
  border-radius: 12px;
  margin-bottom: 22px;
  position: relative;
  overflow: hidden;
}
.hd h1 {
  font-size: 22pt;
  font-family: 'DejaVu Serif', Georgia, serif;
  margin-bottom: 4px;
}
.hd .tag {
  font-size: 9pt;
  opacity: 0.85;
  text-transform: uppercase;
  letter-spacing: 0.16em;
}
.hd .meta {
  font-size: 9pt;
  margin-top: 10px;
  opacity: 0.92;
}
h1 {
  font-size: 16pt;
  color: #0F172A;
  margin: 22px 0 8px;
  padding-bottom: 6px;
  border-bottom: 2px solid #BFDBFE;
}
h2 {
  font-size: 13pt;
  color: #0052FF;
  margin: 18px 0 8px;
  padding-left: 10px;
  border-left: 3px solid #0EA5E9;
}
h3 {
  font-size: 11pt;
  color: #0F172A;
  margin: 14px 0 6px;
}
p {
  margin-bottom: 6px;
}
ul, ol {
  padding-left: 22px;
  margin-bottom: 8px;
}
li {
  margin-bottom: 3px;
}
strong {
  color: #0F172A;
  font-weight: 700;
}
code {
  font-family: 'DejaVu Sans Mono', 'Courier New', monospace;
  font-size: 9pt;
  background: #F1F5F9;
  padding: 1px 5px;
  border-radius: 3px;
  color: #0052FF;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0 14px;
  font-size: 9pt;
  border-radius: 6px;
  overflow: hidden;
}
th {
  background: linear-gradient(180deg, #0F172A 0%, #1E3A8A 100%);
  color: #fff;
  padding: 6px 9px;
  text-align: left;
  font-weight: 600;
  border-bottom: none;
}
td {
  padding: 5px 9px;
  border-bottom: 1px solid #E2E8F0;
  vertical-align: top;
}
tr:nth-child(even) td {
  background: #F8FAFC;
}
.ft {
  margin-top: 28px;
  padding-top: 12px;
  border-top: 1px solid #E2E8F0;
  font-size: 8.5pt;
  color: #94A3B8;
  display: flex;
  justify-content: space-between;
}
"""


def main() -> None:
    if not MD_PATH.exists():
        print(f"ERRO: nao encontrei {MD_PATH}")
        sys.exit(1)

    md_text = MD_PATH.read_text(encoding="utf-8")
    body = md_lib.markdown(md_text, extensions=["tables", "fenced_code"])

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatorio Consolidado - OrgConc</title>
<style>{CSS}</style>
</head>
<body>
  <div class="hd">
    <h1>ORGATEC</h1>
    <div class="tag">Contabilidade &amp; Auditoria - Conciliacao Bancaria</div>
    <div class="meta">Gerado em {agora} - Sistema OrgConc/OrgNeural2</div>
  </div>
  {body}
  <div class="ft">
    <span>(c) ORGATEC Contabilidade e Auditoria - orgatec.cloud@gmail.com</span>
    <span>OrgConc v0.5.0</span>
  </div>
</body>
</html>
"""

    HTML_FALLBACK.write_text(html, encoding="utf-8")

    # Tentativa 1: WeasyPrint (pode falhar se libpango/libgobject conflitam)
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(PDF_PATH))
        print(f"PDF salvo em: {PDF_PATH} (via WeasyPrint)")
        return
    except Exception as exc:
        print(f"WeasyPrint indisponivel ({type(exc).__name__}). Tentando Playwright...")

    # Tentativa 2: Playwright (Chromium headless)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(
                path=str(PDF_PATH),
                format="A4",
                margin={"top": "18mm", "right": "16mm", "bottom": "18mm", "left": "16mm"},
                print_background=True,
                display_header_footer=False,
            )
            browser.close()
        print(f"PDF salvo em: {PDF_PATH} (via Playwright/Chromium)")
        return
    except Exception as exc:
        print(f"Playwright falhou ({type(exc).__name__}: {exc}).")
        print(f"HTML imprimivel salvo em: {HTML_FALLBACK}")
        print("Abra-o no navegador e use Ctrl+P -> Salvar como PDF.")


if __name__ == "__main__":
    main()
