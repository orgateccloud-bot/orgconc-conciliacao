"""Gera um LAUDO MODELO (dados zerados / anonimizados, com códigos) — XLSX + HTML + PDF.

SEM dados de cliente: a empresa e as contrapartes são placeholders codificados
(EMPRESA MODELO, CNPJ 00.000.000/0000-00, contrapartes COD-NNN). Serve para revisar
o VISUAL de todas as páginas/abas do laudo de forma reproduzível e segura.

    python scripts/laudo_modelo.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.matchers.cascata import Transacao  # noqa: E402
from api.services import laudo_forense as L  # noqa: E402

OUT_DIR = Path(r"C:\Users\Veloso\Downloads")

# Empresa EM BRANCO (formulário a preencher) — nenhum dado real nem de exemplo.
EMPRESA_MODELO = {
    "razao_social": "—",
    "razao_anterior": "—",
    "nome_fantasia": "—",
    "cnpj": "—",
    "cnpj_basico": "",
    "data_abertura": "—",
    "situacao": "—",
    "porte_declarado": "—",
    "natureza_juridica": "—",
    "capital_social": 0.0,
    "cnae_principal": "—",
    "cnae_secundario": "—",
    "endereco_sede": "—",
    "endereco_admin": "—",
    "email": "—",
    "telefones": "—",
    "socio_nome": "—",
    "socio_cpf": "—",
    "socio_quotas": "—",
    "socio_nascimento": "—",
    "socio_endereco": "—",
    "ultima_alteracao": "—",
}


def _tx(data: str, valor: float, nome: str, memo: str) -> Transacao:
    return Transacao(
        data=data, tipo="DEBIT" if valor < 0 else "CREDIT", valor=valor,
        fitid=f"{data}|{valor}|{nome}", memo=memo, nome=nome,
        conta="AG 0000-0 / CC 00000-0",
    )


# Transações ZERADAS: 1 por mês (3 meses) só para a estrutura/abas renderizarem.
# Valor 0,00 e sem contraparte — o laudo sai como FORMULÁRIO EM BRANCO.
PLACEHOLDERS = [
    _tx("2026-01-15", 0.0, "—", "—"),
    _tx("2026-02-15", 0.0, "—", "—"),
    _tx("2026-03-15", 0.0, "—", "—"),
]


async def main() -> None:
    L.EMPRESA = EMPRESA_MODELO
    todos, saldos = L.montar_dados(PLACEHOLDERS)
    wb, stats = L.gerar_laudo_workbook(todos, saldos, {})

    base = OUT_DIR / "LAUDO_MODELO"
    base.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(base.with_suffix(".xlsx")))
    print(f"XLSX: {base.with_suffix('.xlsx')} ({len(wb.sheetnames)} abas)")

    md, _ = L.gerar_md(stats)
    base.with_suffix(".md").write_text(md, encoding="utf-8")
    html = L.gerar_html(md, stats.get("periodo_str", ""))
    base.with_suffix(".html").write_text(html, encoding="utf-8")
    print(f"MD/HTML: {base.with_suffix('.html')}")
    if await L.gerar_pdf(html, base.with_suffix(".pdf")):
        print(f"PDF: {base.with_suffix('.pdf')}")


if __name__ == "__main__":
    asyncio.run(main())
