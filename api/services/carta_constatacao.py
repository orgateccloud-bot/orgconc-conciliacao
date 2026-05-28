"""Geração automática da Carta de Constatação a partir do banco.

Sprint 5 do Plano de Integração Fiscal.

Pega dados do cliente + score de conformidade + risco tributário e
renderiza um template Markdown/HTML com 8 Constatações parametrizáveis.

Saída: dict com chaves 'markdown', 'html' (preparado para PDF via Playwright).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Cliente, ConformidadeFornecedor

log = logging.getLogger("orgconc.carta")


def _data_extenso() -> str:
    s = datetime.now().strftime("%d de %B de %Y")
    for en, pt in [
        ("January", "janeiro"), ("February", "fevereiro"), ("March", "marco"),
        ("April", "abril"), ("May", "maio"), ("June", "junho"),
        ("July", "julho"), ("August", "agosto"), ("September", "setembro"),
        ("October", "outubro"), ("November", "novembro"), ("December", "dezembro"),
    ]:
        s = s.replace(en, pt)
    return s


def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def coletar_dados_cliente(
    db: AsyncSession,
    cliente_id: uuid.UUID,
) -> dict:
    cliente = (
        await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    ).scalar_one_or_none()
    if not cliente:
        raise ValueError(f"Cliente não encontrado: {cliente_id}")

    rows = (
        await db.execute(
            select(ConformidadeFornecedor).where(
                ConformidadeFornecedor.cliente_id == cliente_id
            )
        )
    ).scalars().all()

    # Agregações
    risco_total = sum(float(r.risco_tributario_anual or 0) for r in rows)
    by_classe: dict[str, float] = {"BAIXO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 0}
    count_classe: dict[str, int] = {"BAIXO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 0}
    criticos: list[ConformidadeFornecedor] = []
    for r in rows:
        c = r.risco_classe
        by_classe[c] = by_classe.get(c, 0) + float(r.risco_tributario_anual or 0)
        count_classe[c] = count_classe.get(c, 0) + 1
        if c == "CRITICO":
            criticos.append(r)

    return {
        "cliente": cliente,
        "total_fornecedores": len(rows),
        "risco_total": risco_total,
        "by_classe": by_classe,
        "count_classe": count_classe,
        "criticos": sorted(criticos, key=lambda x: -float(x.risco_tributario_anual or 0))[:10],
    }


def renderizar_carta_md(dados: dict, versao: str = "auto-1") -> str:
    """Renderiza Markdown da Carta de Constatação com base nos dados."""
    cliente = dados["cliente"]
    hoje = _data_extenso()
    ref = f"CONST-AUTO-{datetime.now().strftime('%Y%m%d-%H%M')}-{versao}"

    md = [
        "# CARTA DE CONSTATACAO",
        "",
        "**Memorando Tecnico-Juridico de Auditoria Fiscal — Versao Automatica**",
        "",
        "---",
        "",
        "**De:** ORGATEC CONTABILIDADE E AUDITORIA LTDA",
        "",
        f"**Para:** {cliente.nome} — CNPJ {cliente.cnpj or 'n/a'}",
        "",
        f"**Referencia:** {ref}",
        "",
        f"**Assunto:** Constatacoes formais de auditoria fiscal — cruzamento NF-e/CT-e × OFX.",
        "",
        f"**Local e Data:** Goiania-GO, {hoje}",
        "",
        "---",
        "",
        "## 1. Preambulo",
        "",
        f"Prezado(a),",
        "",
        f"Apresentamos as constatacoes da auditoria fiscal cruzada para a empresa **{cliente.nome}**, ",
        f"baseada em {dados['total_fornecedores']} fornecedores analisados. O risco tributario anualizado ",
        f"consolidado totaliza **{_fmt_brl(dados['risco_total'])}**.",
        "",
        "## 2. Sumario por Classe de Risco",
        "",
        "| Classe | Fornecedores | Risco Anualizado |",
        "|--------|:------------:|------------------:|",
    ]
    for classe in ("CRITICO", "ALTO", "MEDIO", "BAIXO"):
        n = dados["count_classe"].get(classe, 0)
        v = dados["by_classe"].get(classe, 0.0)
        md.append(f"| {classe} | {n} | {_fmt_brl(v)} |")
    md.append(f"| **TOTAL** | **{dados['total_fornecedores']}** | **{_fmt_brl(dados['risco_total'])}** |")
    md.append("")

    if dados["criticos"]:
        md += [
            "## 3. Top 10 Fornecedores CRITICOS",
            "",
            "| # | Fornecedor | CNPJ | Volume Pago | Volume NF | Conformidade | Risco/Ano |",
            "|:-:|---|---|---:|---:|---:|---:|",
        ]
        for i, f in enumerate(dados["criticos"], 1):
            md.append(
                f"| {i} | {(f.razao_social or '?')[:40]} | {f.cnpj_fornecedor} | "
                f"{_fmt_brl(float(f.volume_pago or 0))} | "
                f"{_fmt_brl(float(f.volume_nf or 0))} | "
                f"{float(f.conformidade_pct or 0):.1f}% | "
                f"{_fmt_brl(float(f.risco_tributario_anual or 0))} |"
            )
        md.append("")

    md += [
        "## 4. Fundamentacao Normativa Aplicada",
        "",
        "- **RIR/2018 art. 311** — despesa indedutivel quando sem documento fiscal idoneo",
        "- **RIR/2018 art. 226** — adicao obrigatoria no LALUR",
        "- **Lei 8.846/1994 art. 7** — multa 300% sobre operacao sem nota",
        "- **Decreto 8.324/2014** — CT-e obrigatorio para transporte de cargas",
        "- **Convenio ICMS 26/2008** — substituicao tributaria do tomador (transporte autonomo)",
        "- **IN RFB 1.234/2012** — retencoes na fonte (PIS+COFINS+CSLL+IRRF)",
        "- **Lei 8.137/1990** — crimes contra a ordem tributaria",
        "- **CTN art. 138** — denuncia espontanea (afasta multa de oficio)",
        "",
        "## 5. Recomendacoes Formais",
        "",
        "1. **Solicitar NF-es faltantes** dos fornecedores CRITICOS (prazo 30 dias);",
        "2. **Verificar SEFAZ Distribuicao DFe** para documentos nao baixados (30 dias);",
        "3. **Suspender pagamentos** sem documento fiscal correspondente (45 dias);",
        "4. **Recolher diferencas de IRPJ+CSLL** via denuncia espontanea (90 dias);",
        "5. **Implantar controle previo** de NF-e/CT-e no fluxo de pagamentos (60 dias);",
        "6. **Treinar equipe financeira** sobre obrigatoriedade documental em Lucro Real (90 dias).",
        "",
        "## 6. Conclusao",
        "",
        f"A empresa {cliente.nome} apresenta passivo tributario potencial anualizado ",
        f"de **{_fmt_brl(dados['risco_total'])}**, sendo necessarias acoes imediatas para ",
        "mitigacao. Permanecemos a disposicao para acompanhar a regularizacao.",
        "",
        "Atenciosamente,",
        "",
        "ORGATEC CONTABILIDADE E AUDITORIA LTDA",
        "",
        "---",
        "",
        f"*Documento gerado automaticamente em {hoje} pelo sistema OrgConc/OrgNeural2.*",
    ]
    return "\n".join(md)


_CSS_CARTA = """
@page { size: A4; margin: 22mm 18mm 22mm 18mm;
  @bottom-right { content: "Pagina " counter(page) " de " counter(pages); font-size: 9px; color: #6B7280; }
  @bottom-left { content: "ORGATEC · Carta Auto-Gerada"; font-size: 9px; color: #6B7280; }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DejaVu Serif', Georgia, serif; font-size: 11pt; color: #1a202c; line-height: 1.65; }
.hd { background: linear-gradient(135deg, #0F172A, #0B1B3D 45%, #0052FF); color: #fff;
      padding: 28px 32px; border-radius: 4px; margin-bottom: 28px; }
.hd h1 { font-size: 24pt; }
h1 { font-size: 16pt; color: #0F172A; margin: 28px 0 12px; padding-bottom: 8px;
     border-bottom: 3px double #0052FF; text-align: center; }
h2 { font-size: 13pt; color: #0F172A; margin: 24px 0 10px; padding: 10px 14px;
     background: #F0F7FF; border-left: 4px solid #0052FF; }
table { width: 100%; border-collapse: collapse; margin: 12px 0 18px; font-size: 10pt;
        font-family: 'DejaVu Sans', sans-serif; }
th { background: #0F172A; color: #fff; padding: 8px 12px; text-align: left; }
td { padding: 7px 12px; border-bottom: 1px solid #E2E8F0; }
tr:nth-child(even) td { background: #F8FAFC; }
strong { color: #0F172A; font-weight: 700; }
ul, ol { padding-left: 22px; margin-bottom: 12px; }
"""


def renderizar_html(md_text: str, titulo: str = "Carta de Constatacao") -> str:
    """Converte Markdown em HTML estilizado para PDF."""
    try:
        import markdown as mdlib
        body = mdlib.markdown(md_text, extensions=["tables", "fenced_code"])
    except ImportError:
        body = f"<pre>{md_text}</pre>"
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>{titulo}</title><style>{_CSS_CARTA}</style></head>
<body>
<div class="hd">
  <h1>ORGATEC</h1>
  <div style="margin-top:6px;font-size:10pt;opacity:.9;text-transform:uppercase;letter-spacing:.18em">
    Carta Auto-Gerada · Sistema OrgConc
  </div>
  <div style="margin-top:8px;font-size:9pt;opacity:.85">Gerado em {agora}</div>
</div>
{body}
</body></html>"""


async def gerar_carta_automatica(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    versao: str = "auto-1",
) -> dict:
    """Pipeline completo: coleta dados + renderiza MD + HTML."""
    dados = await coletar_dados_cliente(db, cliente_id)
    md_text = renderizar_carta_md(dados, versao=versao)
    html = renderizar_html(md_text, titulo=f"Carta {dados['cliente'].nome}")
    return {
        "cliente_id": str(cliente_id),
        "cliente_nome": dados["cliente"].nome,
        "versao": versao,
        "risco_total": dados["risco_total"],
        "total_fornecedores": dados["total_fornecedores"],
        "markdown": md_text,
        "html": html,
    }


async def renderizar_pdf_async(html: str) -> Optional[bytes]:
    """Gera PDF via Playwright (assíncrono)."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html, wait_until="load")
            pdf_bytes = await page.pdf(
                format="A4",
                margin={"top": "22mm", "right": "18mm", "bottom": "22mm", "left": "18mm"},
                print_background=True,
            )
            await browser.close()
        return pdf_bytes
    except Exception:
        log.exception("Falha ao renderizar PDF")
        return None
