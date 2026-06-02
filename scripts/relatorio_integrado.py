"""CLI do Laudo Integrado de Auditoria Bancária (11 abas) — modelo PRINCIPAL.

Wrapper fino sobre `api.services.laudo_forense` (núcleo reusável também pela API).
Gera XLSX + MD + HTML + PDF a partir de uma pasta de extratos OFX + enriquecimento.

    python scripts/relatorio_integrado.py --pasta <dir> --conta <id> \\
        --empresa-cnpj <14d> --tag <nome> [--enrich-all]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.services import laudo_forense as L  # noqa: E402

PASTA_DEFAULT = r"C:\Users\Veloso\Desktop\locar"
OUT_DIR = Path(r"C:\Users\Veloso\Downloads")


async def main_async() -> None:
    ap = argparse.ArgumentParser(description="Laudo Integrado de Auditoria Bancaria (11 abas) — OrgConc")
    ap.add_argument("--pasta", default=PASTA_DEFAULT, help="pasta com os arquivos .ofx")
    ap.add_argument("--conta", default="", help="escopar a uma conta (substring do ID, ex: 158083)")
    ap.add_argument("--empresa-cnpj", default="", help="CNPJ da entidade auditada (14 dígitos)")
    ap.add_argument("--tag", default="laudo", help="sufixo dos arquivos de saída")
    ap.add_argument("--enrich-all", action="store_true", help="enriquecer TODOS os CNPJs (senão top-300)")
    args = ap.parse_args()

    base = OUT_DIR / f"RELATORIO_INTEGRADO_{args.tag}"
    print(f"== Laudo Integrado == fonte: {args.pasta}")
    todos, saldos, cache = await L.coletar_dados(args.pasta, args.conta, args.empresa_cnpj, args.enrich_all)
    if not todos:
        print("Nenhuma transacao encontrada — abortando.")
        return

    print("Gerando XLSX (11 abas)...")
    wb, stats = L.gerar_laudo_workbook(todos, saldos, cache)
    out_xlsx = base.with_suffix(".xlsx")
    wb.save(str(out_xlsx))
    print(f"  XLSX: {out_xlsx}")

    print("Gerando MD / HTML / PDF...")
    md, _ = L.gerar_md(stats)
    base.with_suffix(".md").write_text(md, encoding="utf-8")
    html = L.gerar_html(md, stats.get("periodo_str", ""))
    base.with_suffix(".html").write_text(html, encoding="utf-8")
    print(f"  MD/HTML: {base.with_suffix('.md')}")
    if await L.gerar_pdf(html, base.with_suffix(".pdf")):
        print(f"  PDF:  {base.with_suffix('.pdf')}")


if __name__ == "__main__":
    asyncio.run(main_async())
