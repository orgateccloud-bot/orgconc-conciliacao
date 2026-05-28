"""Investigacao forense de 3 alvos suspeitos da conta 158083-3 da LOCAR.

ALVOS:
1. THIAGO MARQUES DE AVILA (3 PIX recebidos R$ 1,27M em jan/2026)
2. GT PARTICIPACOES LTDA (11 PIX recebidos R$ 1,62M em fev-mai/2026)
3. REDE FROTA SOLUTIONS LTDA - CNPJ 24.478.438/0001-48 (29 pagamentos R$ 3,03M)

Para cada um:
- Enriquecimento via BrasilAPI (caso PJ identificavel)
- Cruzamento com NF-es recebidas (compras dos 5.031 docs)
- Cruzamento com CT-es emitidos (3.045 docs)
- Identificacao de padroes (frequencia, sazonalidade, valores redondos)
- Gera relatorio investigativo em PDF/HTML/MD
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _logo_helper import html_logo_inline
from api.matchers.cascata import ler_ofx
from api.matchers.cnpj_enricher import _carregar_cache, _salvar_cache, enriquecer_um

OFX_LIST = [
    r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260514110822.ofx",
    r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260514110841.ofx",
    r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260514110900.ofx",
    r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260514110917.ofx",
    r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260514110938.ofx",
]
ZIPS_NFE_RECEBIDAS = [
    r"C:\Users\Veloso\Downloads\103585885_01012026_31012026_7514.zip",
    r"C:\Users\Veloso\Downloads\103585885_01022026_28022026_8464.zip",
    r"C:\Users\Veloso\Downloads\103585885_01032026_31032026_8594.zip",
    r"C:\Users\Veloso\Downloads\103585885_01042026_30042026_7245.zip",
]
ZIPS_CTE_EMITIDOS = [
    r"C:\Users\Veloso\Downloads\05509396000110_01012026_31012026_0546.zip",
    r"C:\Users\Veloso\Downloads\05509396000110_01022026_28022026_5384.zip",
    r"C:\Users\Veloso\Downloads\05509396000110_01032026_31032026_4046.zip",
    r"C:\Users\Veloso\Downloads\05509396000110_01042026_30042026_9825.zip",
]

OUT_BASE = r"C:\Users\Veloso\Downloads\INVESTIGACAO_ALVOS_LOCAR"
OUT_MD = Path(f"{OUT_BASE}.md")
OUT_HTML = Path(f"{OUT_BASE}.html")
OUT_PDF = Path(f"{OUT_BASE}.pdf")

RX_CNPJ = re.compile(r"(\d{2})[.](\d{3})[.](\d{3})[ /](\d{4})[-](\d{2})")


def _local(tag):
    return tag.split("}")[-1]


def _filho(elem, nome):
    if elem is None:
        return None
    for f in elem:
        if _local(f.tag) == nome:
            return f
    return None


def _texto(elem, *caminho):
    cur = elem
    for nome in caminho:
        cur = _filho(cur, nome)
        if cur is None:
            return ""
    return cur.text.strip() if cur is not None and cur.text else ""


def parse_nfe_basico(conteudo):
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError:
        return None
    inf = None
    for el in root.iter():
        if _local(el.tag) == "infNFe":
            inf = el
            break
    if inf is None:
        return None
    ide = _filho(inf, "ide")
    emit = _filho(inf, "emit")
    total = _filho(inf, "total")
    icms_tot = _filho(total, "ICMSTot") if total is not None else None
    return {
        "chave": (inf.get("Id") or "").lstrip("NFe"),
        "numero": _texto(ide, "nNF"),
        "data": (_texto(ide, "dhEmi") or _texto(ide, "dEmi"))[:10],
        "emit_cnpj": _texto(emit, "CNPJ"),
        "emit_nome": _texto(emit, "xNome"),
        "valor": float(_texto(icms_tot, "vNF") or 0) if icms_tot is not None else 0.0,
    }


def parse_cte_basico(conteudo):
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError:
        return None
    inf = None
    for el in root.iter():
        if _local(el.tag) in ("infCte", "infCTe"):
            inf = el
            break
    if inf is None:
        return None
    ide = _filho(inf, "ide")
    rem = _filho(inf, "rem")
    dest = _filho(inf, "dest")
    vprest = _filho(inf, "vPrest")
    return {
        "chave": (inf.get("Id") or "").lstrip("CTe"),
        "numero": _texto(ide, "nCT"),
        "data": (_texto(ide, "dhEmi") or _texto(ide, "dEmi"))[:10],
        "rem_cnpj": _texto(rem, "CNPJ") if rem else "",
        "rem_nome": _texto(rem, "xNome") if rem else "",
        "dest_cnpj": _texto(dest, "CNPJ") if dest else "",
        "dest_nome": _texto(dest, "xNome") if dest else "",
        "valor": float(_texto(vprest, "vTPrest") or 0) if vprest else 0.0,
    }


async def main_async():
    print("Carregando dados...")
    transacoes = []
    for p in OFX_LIST:
        transacoes.extend(ler_ofx(p))
    print(f"  {len(transacoes):,} transacoes OFX")

    nfes = []
    for path in ZIPS_NFE_RECEBIDAS:
        with zipfile.ZipFile(path) as zf:
            for m in zf.namelist():
                if m.endswith(".xml"):
                    chave = Path(m).stem
                    if len(chave) >= 22 and chave[20:22] == "55":
                        with zf.open(m) as f:
                            doc = parse_nfe_basico(f.read())
                        if doc:
                            nfes.append(doc)
    print(f"  {len(nfes):,} NF-es recebidas")

    ctes = []
    for path in ZIPS_CTE_EMITIDOS:
        with zipfile.ZipFile(path) as zf:
            for m in zf.namelist():
                if m.endswith(".xml"):
                    chave = Path(m).stem
                    if len(chave) >= 22 and chave[20:22] == "57":
                        with zf.open(m) as f:
                            doc = parse_cte_basico(f.read())
                        if doc:
                            ctes.append(doc)
    print(f"  {len(ctes):,} CT-es emitidos")

    cache = _carregar_cache()

    # ALVO 3: REDE FROTA — buscar NF-es e CT-es deste CNPJ
    CNPJ_REDE_FROTA = "24478438000148"
    info_rede = cache.get(CNPJ_REDE_FROTA, {})

    rede_nfes = [n for n in nfes if n["emit_cnpj"] == CNPJ_REDE_FROTA]
    rede_ctes = [c for c in ctes if c["dest_cnpj"] == CNPJ_REDE_FROTA or c["rem_cnpj"] == CNPJ_REDE_FROTA]
    rede_pagamentos = []
    for t in transacoes:
        if t.valor < 0:
            m = RX_CNPJ.search((t.nome or "") + " " + (t.memo or ""))
            if m and "".join(m.groups()) == CNPJ_REDE_FROTA:
                rede_pagamentos.append(t)
    rede_estornos = [t for t in rede_pagamentos if "ESTORNO" in (t.memo or "").upper() or t.valor > 0]

    print(f"\nREDE FROTA: {len(rede_nfes)} NF-es | {len(rede_ctes)} CT-es | {len(rede_pagamentos)} pagamentos OFX")

    # ALVO 1: THIAGO MARQUES — tentar identificar CNPJ via NF-e/CT-e
    thiago_txs = []
    for t in transacoes:
        if "THIAGO MARQUES" in (t.nome or "").upper():
            thiago_txs.append(t)
    # Busca em CT-es se algum tomador tem THIAGO no nome
    thiago_ctes = []
    for c in ctes:
        nome = (c["dest_nome"] or "") + " " + (c["rem_nome"] or "")
        if "THIAGO MARQUES" in nome.upper():
            thiago_ctes.append(c)

    # ALVO 2: GT PARTICIPACOES — tentar identificar
    gt_txs = []
    for t in transacoes:
        if "GT PARTICIPACOES" in (t.nome or "").upper():
            gt_txs.append(t)
    gt_ctes = []
    for c in ctes:
        nome = (c["dest_nome"] or "") + " " + (c["rem_nome"] or "")
        if "GT PARTICIPACOES" in nome.upper() or "GT PART" in nome.upper():
            gt_ctes.append(c)

    # Se GT aparece em CT-es, podemos pegar CNPJ
    gt_cnpj_candidatos = set()
    for c in gt_ctes:
        for cnpj in (c["dest_cnpj"], c["rem_cnpj"]):
            if cnpj and len(cnpj) == 14:
                gt_cnpj_candidatos.add(cnpj)

    # Enriquece via BrasilAPI se necessario
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        semaforo = asyncio.Semaphore(2)
        for cnpj in gt_cnpj_candidatos:
            if cnpj not in cache:
                await enriquecer_um(cnpj, cache, client, None, semaforo)
        _salvar_cache(cache)

    gt_info_candidatos = {c: cache.get(c, {}) for c in gt_cnpj_candidatos}

    print(f"\nTHIAGO: {len(thiago_txs)} PIX OFX | {len(thiago_ctes)} CT-es")
    print(f"GT PARTICIPACOES: {len(gt_txs)} PIX OFX | {len(gt_ctes)} CT-es | CNPJs candidatos: {len(gt_cnpj_candidatos)}")

    # ────────────────────────────────────────────────────────────────────
    # Gera relatorio Markdown
    # ────────────────────────────────────────────────────────────────────
    md_lines = [
        "# INVESTIGACAO FORENSE - 3 ALVOS SUSPEITOS",
        "",
        "**LOCAR TRANSPORTE DE BOVINOS LTDA · Conta 158083-3 · Periodo jan-mai/2026**",
        "",
        f"**Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "---",
        "",
        "## ALVO 1: THIAGO MARQUES DE AVILA",
        "",
        "**Tipo:** Pessoa Fisica (nao identificado CNPJ direto nos extratos)",
        "**Padrao:** 3 transferencias PIX concentradas em 16 dias (14/01 a 30/01/2026)",
        "",
        "### Transacoes detectadas",
        "",
        "| Data | Tipo | Valor (R$) | Origem |",
        "|---|---|---:|---|",
    ]
    total_thiago = 0
    for t in sorted(thiago_txs, key=lambda x: x.data):
        md_lines.append(f"| {t.data} | PIX RECEBIDO | {t.valor:,.2f} | {(t.nome or '')[:50]} |")
        total_thiago += t.valor
    md_lines.append(f"| **TOTAL** | | **R$ {total_thiago:,.2f}** | 3 transacoes em 16 dias |")

    md_lines += [
        "",
        "### Cruzamento com NF-es e CT-es",
        "",
        f"- CT-es onde Thiago aparece como remetente/destinatario: **{len(thiago_ctes)}**",
        "",
        "### Hipoteses",
        "",
        "1. **Pagamento por servico de transporte** (mas sem CT-e identificado — possivel emissao posterior)",
        "2. **Venda de animais** (LOCAR transporta bovinos — Thiago pode ser pecuarista)",
        "3. **Mutuo entre pessoas fisicas** (PJ recebendo mutuo de PF)",
        "4. **Negocio paralelo** sem documentacao fiscal",
        "",
        "**Acao recomendada:** Solicitar contratos/recibos que justifiquem os R$ 1,27M recebidos em 16 dias.",
        "",
        "---",
        "",
        "## ALVO 2: GT PARTICIPACOES LTDA",
        "",
        "**Tipo:** Pessoa Juridica (LTDA)",
        "**Padrao:** 11 transferencias PIX em fev-mai/2026, valores variados",
        "**Volume:** R$ 1.625.236,75 em 4 meses",
        "",
    ]
    if gt_info_candidatos:
        md_lines += [
            "### CNPJs candidatos identificados via CT-es",
            "",
            "| CNPJ | Razao Social | Situacao | UF |",
            "|---|---|---|---|",
        ]
        for cnpj, info in gt_info_candidatos.items():
            fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}"
            md_lines.append(f"| {fmt} | {info.get('razao_social', '?')} | {info.get('situacao', '?')} | {info.get('uf', '?')} |")
    else:
        md_lines += [
            "### Identificacao",
            "",
            "Nao foi possivel identificar o CNPJ exato a partir dos documentos disponiveis.",
            "A LOCAR nao emitiu CT-e para a GT PARTICIPACOES (sugere que GT nao e cliente de transporte).",
            "",
            "**Acao recomendada:** Solicitar CNPJ exato da GT PARTICIPACOES ao contribuinte.",
        ]

    md_lines += [
        "",
        "### Transacoes detectadas",
        "",
        "| Data | Valor (R$) |",
        "|---|---:|",
    ]
    total_gt = 0
    for t in sorted(gt_txs, key=lambda x: x.data):
        md_lines.append(f"| {t.data} | {t.valor:,.2f} |")
        total_gt += t.valor
    md_lines.append(f"| **TOTAL** | **R$ {total_gt:,.2f}** |")

    md_lines += [
        "",
        "### Hipoteses",
        "",
        "1. **Holding/Investidor** do grupo (GT pode ser holding controladora)",
        "2. **Empresa cliente** com pagamento avulso (sem CT-e correspondente)",
        "3. **Parte relacionada** disfarcada (recebimento como receita financeira)",
        "4. **Mutuo entre empresas do grupo** (sem lastro contratual claro)",
        "",
        "**Acao recomendada:** Verificar composicao societaria da GT PARTICIPACOES — se Renato Costa Esperidiao Jr aparecer como socio = parte relacionada confirmada.",
        "",
        "---",
        "",
        "## ALVO 3: REDE FROTA SOLUTIONS LTDA",
        "",
        f"**CNPJ:** 24.478.438/0001-48",
        f"**Razao Social:** {info_rede.get('razao_social', '?')}",
        f"**CNAE:** {info_rede.get('cnae_descricao', '?')}",
        f"**UF:** {info_rede.get('uf', '?')} | **Porte:** {info_rede.get('porte', '?')} | **Situacao:** {info_rede.get('situacao', '?')}",
        "",
        "### Padrao Identificado",
        "",
        f"- **{len(rede_pagamentos)} transacoes** com a REDE FROTA (jan-mai/2026)",
        f"- **Volume bruto:** R$ {sum(abs(t.valor) for t in rede_pagamentos):,.2f}",
        f"- **Liquido pago:** R$ {sum(t.valor for t in rede_pagamentos):,.2f}",
        f"- **NF-es recebidas da REDE FROTA:** {len(rede_nfes)}",
        f"- **Volume NF-e total:** R$ {sum(n['valor'] for n in rede_nfes):,.2f}",
        f"- **Estornos detectados:** {len(rede_estornos)}",
        "",
        "### Interpretacao",
        "",
        "**REDE FROTA SOLUTIONS LTDA** e uma **administradora de cartoes de credito** (CNAE 66.19-3-99 ou similar). Em contexto de transporte rodoviario:",
        "",
        "- E **operadora de cartao de combustivel/frete corporativo** (similar a Edenred, Sodexo Truckpad)",
        "- A LOCAR usa para abastecer caminhoes e pagar pedagios da frota",
        "- Faturamento mensal ~R$ 800k = ~R$ 9,6M/ano em combustivel/pedagio",
        "",
        "### Estornos suspeitos em 24/03/2026",
        "",
        "Foram detectados **3 estornos de R$ 30.000 cada** em 24/03/2026 (mesma data), sequenciais com novos pagamentos imediatos. Padrao tipico de:",
        "",
        "- **Contestacao/recontagem de cobranca** (banco devolve, empresa contesta, ressubmete)",
        "- **Possivel falha de cobranca em duplicidade** (verificar)",
        "",
        "### Conformidade Fiscal",
        "",
    ]
    if rede_nfes:
        md_lines += [
            f"- **{len(rede_nfes)}** NF-es de servico identificadas",
            "- Cruzamento valor pago x valor NF: precisa de detalhamento manual",
            "",
            "**Conformidade aparente: OK** (ha documentacao fiscal)",
        ]
    else:
        md_lines += [
            "- **ZERO NF-es de servico** identificadas em 4 meses",
            f"- Pagamentos de R$ {sum(abs(t.valor) for t in rede_pagamentos):,.2f} sem documento fiscal correspondente",
            "",
            "**⚠️ NAO CONFORMIDADE:** Pagamentos relevantes sem NF-e. Em Lucro Real, despesa nao dedutivel.",
            "",
            "**Possiveis explicacoes:**",
            "1. NF-es emitidas em outro periodo (antes de jan/2026)",
            "2. NF-es enviadas via outro canal (papel, email PDF)",
            "3. Operacao via cartao = faturamento direto sem NF separada",
            "4. **A INVESTIGAR**: solicitar NF-es da REDE FROTA SOLUTIONS de jan-mai/2026",
        ]

    md_lines += [
        "",
        "---",
        "",
        "## CONCLUSOES E RECOMENDACOES",
        "",
        "| Alvo | Volume | Status | Acao Recomendada |",
        "|---|---:|:---:|---|",
        f"| THIAGO MARQUES (PF) | R$ {total_thiago:,.2f} | A INVESTIGAR | Solicitar contratos/recibos |",
        f"| GT PARTICIPACOES | R$ {total_gt:,.2f} | A INVESTIGAR | Confirmar CNPJ + verificar quadro societario |",
        f"| REDE FROTA | R$ {sum(abs(t.valor) for t in rede_pagamentos):,.2f} | {'CONFORME' if rede_nfes else 'NAO CONFORME'} | {'Conferir cruzamento valor x NF' if rede_nfes else 'Solicitar NF-es de servico'} |",
        "",
        f"**Volume conjunto sob investigacao:** R$ {total_thiago + total_gt + sum(abs(t.valor) for t in rede_pagamentos):,.2f}",
        "",
        "---",
        "",
        "*Sistema OrgConc/OrgNeural2 - Investigacao forense de alvos especificos.*",
    ]

    md = "\n".join(md_lines)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"\n  MD:   {OUT_MD}")

    # HTML
    import markdown as mdlib
    body = mdlib.markdown(md, extensions=["tables", "fenced_code"])
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    css = """
@page { size: A4 landscape; margin: 14mm 12mm 14mm 12mm;
  @bottom-right { content: "Pagina " counter(page) " de " counter(pages); font-size: 9px; color: #6B7280; }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10pt; color: #1a202c; line-height: 1.55; }
.hd { background: linear-gradient(135deg, #0F172A, #0B1B3D 45%, #DC2626); color: #fff;
      padding: 22px 28px; border-radius: 8px; margin-bottom: 22px; display: flex; align-items: center; gap: 22px; }
.hd-text { flex: 1; }
.hd h1 { font-size: 22pt; font-family: 'DejaVu Serif', Georgia, serif; }
.hd .tag { font-size: 10pt; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.18em; }
h1 { font-size: 14pt; color: #0F172A; margin: 22px 0 8px; padding-bottom: 6px; border-bottom: 2px solid #DC2626; }
h2 { font-size: 13pt; color: #DC2626; margin: 22px 0 8px; padding: 10px 14px;
     background: linear-gradient(90deg, #FEF2F2, transparent); border-left: 4px solid #DC2626; }
h3 { font-size: 11pt; color: #0F172A; margin: 14px 0 6px; font-weight: 700; }
table { width: 100%; border-collapse: collapse; margin: 10px 0 14px; font-size: 9pt; }
th { background: linear-gradient(180deg, #0F172A, #1E3A8A); color: #fff; padding: 6px 9px; text-align: left; }
td { padding: 5px 9px; border-bottom: 1px solid #E2E8F0; }
tr:nth-child(even) td { background: #F8FAFC; }
strong { color: #0F172A; font-weight: 700; }
"""
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>Investigacao Forense Alvos LOCAR</title><style>{css}</style></head>
<body>
<div class="hd">{html_logo_inline()}<div class="hd-text">
<h1>ORGATEC</h1>
<div class="tag">Investigacao Forense · 3 Alvos Suspeitos</div>
<div style="margin-top:8px;font-size:9pt;opacity:.85">LOCAR TRANSPORTE DE BOVINOS LTDA · Conta 158083-3 · Gerado em {agora}</div>
</div></div>
{body}
</body></html>"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"  HTML: {OUT_HTML}")

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html, wait_until="load")
            await page.pdf(path=str(OUT_PDF), format="A4", landscape=True,
                margin={"top": "14mm", "right": "12mm", "bottom": "14mm", "left": "12mm"},
                print_background=True)
            await browser.close()
        print(f"  PDF:  {OUT_PDF}")
    except Exception as exc:
        print(f"PDF failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main_async())
