"""Laudo de Documentos Fiscais (NF-e/CT-e/NFS-e) — relatório baseado SOMENTE nos
documentos fiscais, sem extrato bancário (OFX).

Útil quando se tem os XMLs mas não o extrato, ou para auditar a base documental
isoladamente. Gera um XLSX com:
  1. Resumo        — KPIs + alertas (chaves inválidas, emitentes não-ativos)
  2. Por Fornecedor— emitentes por volume + situação cadastral
  3. Natureza/CFOP — distribuição por natureza de operação e por CFOP
  4. Por Dia       — distribuição temporal
  5. Notas         — detalhe documento a documento
  6. Alertas       — chaves inválidas + canceladas/denegadas + emitentes não-ativos

`situacao_por_cnpj` é opcional (dict CNPJ->situação cadastral) — o router pode
derivá-lo do cache de CNPJ; sem ele, a coluna cadastral fica vazia (sem rede).
"""
from __future__ import annotations

import html as _html
from collections import Counter, defaultdict
from typing import Iterable, Optional

from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side

from api.matchers.xml_fiscal import DocumentoFiscalLido

_NAVY = "0F172A"
_HDR_FILL = PatternFill("solid", fgColor=_NAVY)
_HDR_FONT = Font(color="FFFFFF", bold=True)
_TITULO = Font(bold=True, size=14, color=_NAVY)
_BOLD = Font(bold=True)
_RED = PatternFill("solid", fgColor="FDE2E2")
_AMBER = PatternFill("solid", fgColor="FEF3C7")
_THIN = Border(*[Side(style="thin", color="E2E8F0")] * 4)
_MONEY = "#,##0.00"

ABAS_NOTAS = [
    "1. Resumo", "2. Por Fornecedor", "3. Natureza CFOP",
    "4. Por Dia", "5. Notas", "6. Alertas",
]


def _hdr(ws, row: int, cols: list[str]) -> None:
    for c, t in enumerate(cols, 1):
        cell = ws.cell(row=row, column=c, value=t)
        cell.fill = _HDR_FILL
        cell.font = _HDR_FONT
        cell.border = _THIN


def _larguras(ws, larguras: dict[str, int]) -> None:
    for col, w in larguras.items():
        ws.column_dimensions[col].width = w


def _situacao_nao_ativa(sit: str) -> bool:
    return bool(sit) and "ATIVA" not in sit.upper()


def gerar_laudo_notas_workbook(
    documentos: Iterable[DocumentoFiscalLido],
    situacao_por_cnpj: Optional[dict[str, str]] = None,
) -> tuple[Workbook, dict]:
    """Gera o XLSX do laudo de notas. Retorna (workbook, stats)."""
    docs = [d for d in documentos if d.chave]
    sit_map = situacao_por_cnpj or {}

    def sit_cad(cnpj: str) -> str:
        return sit_map.get(cnpj) or sit_map.get(cnpj[:8], "") if cnpj else ""

    total = sum(d.valor_total for d in docs)
    icms = sum(d.valor_icms for d in docs)
    pis = sum(d.valor_pis for d in docs)
    cofins = sum(d.valor_cofins for d in docs)
    iss = sum(d.valor_iss for d in docs)
    por_situacao = Counter(d.situacao for d in docs)
    invalidas = [d for d in docs if d.chave_valida is False]
    canceladas = [d for d in docs if d.situacao in ("CANCELADA", "DENEGADA")]
    nao_ativos = [d for d in docs if _situacao_nao_ativa(sit_cad(d.emit_cnpj))]
    datas = sorted(d.data_emissao for d in docs if d.data_emissao)

    wb = Workbook()

    # ── Aba 1: Resumo ────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "1. Resumo"
    ws["A1"] = "ORGATEC · Laudo de Documentos Fiscais (NF-e/CT-e/NFS-e)"
    ws["A1"].font = _TITULO
    kpis = [
        ("Total de documentos", len(docs)),
        ("Periodo", f"{datas[0]} a {datas[-1]}" if datas else "-"),
        ("Fornecedores (emitentes) distintos", len({d.emit_cnpj for d in docs if d.emit_cnpj})),
        ("Volume total documentado", total),
        ("ICMS total", icms), ("PIS total", pis),
        ("COFINS total", cofins), ("ISS total", iss),
        ("Autorizadas", por_situacao.get("AUTORIZADA", 0)),
        ("Canceladas", por_situacao.get("CANCELADA", 0)),
        ("Denegadas", por_situacao.get("DENEGADA", 0)),
        ("[!] Chaves invalidas (mod-11)", len(invalidas)),
        ("[!] Emitentes nao-ativos (cadastro)", len(nao_ativos)),
    ]
    r = 3
    for k, v in kpis:
        ws.cell(row=r, column=1, value=k).font = _BOLD
        cell = ws.cell(row=r, column=2, value=v)
        if isinstance(v, (int, float)) and ("Volume" in k or "total" in k.lower()):
            cell.number_format = _MONEY
        if k.startswith("[!]") and isinstance(v, int) and v > 0:
            ws.cell(row=r, column=1).fill = _RED
            ws.cell(row=r, column=2).fill = _RED
        r += 1
    _larguras(ws, {"A": 40, "B": 22})

    # ── Aba 2: Por Fornecedor ────────────────────────────────────────────
    ws = wb.create_sheet("2. Por Fornecedor")
    agg: dict[str, dict] = defaultdict(lambda: {"n": 0, "vol": 0.0, "icms": 0.0, "nome": ""})
    for d in docs:
        a = agg[d.emit_cnpj]
        a["n"] += 1
        a["vol"] += d.valor_total
        a["icms"] += d.valor_icms
        a["nome"] = d.emit_nome or a["nome"]
    _hdr(ws, 1, ["CNPJ", "Razao Social", "Qtd", "Volume (R$)", "ICMS (R$)", "Situacao Cadastral"])
    r = 2
    for cnpj, a in sorted(agg.items(), key=lambda kv: -kv[1]["vol"]):
        sc = sit_cad(cnpj)
        ws.cell(row=r, column=1, value=cnpj)
        ws.cell(row=r, column=2, value=(a["nome"] or "")[:40])
        ws.cell(row=r, column=3, value=a["n"])
        ws.cell(row=r, column=4, value=round(a["vol"], 2)).number_format = _MONEY
        ws.cell(row=r, column=5, value=round(a["icms"], 2)).number_format = _MONEY
        ws.cell(row=r, column=6, value=sc or "(sem cadastro)")
        if _situacao_nao_ativa(sc):
            for col in range(1, 7):
                ws.cell(row=r, column=col).fill = _AMBER
        r += 1
    _larguras(ws, {"A": 18, "B": 42, "C": 8, "D": 16, "E": 14, "F": 20})
    ws.freeze_panes = "A2"

    # ── Aba 3: Natureza de Operacao + CFOP ───────────────────────────────
    ws = wb.create_sheet("3. Natureza CFOP")
    nat: dict[str, dict] = defaultdict(lambda: {"n": 0, "vol": 0.0})
    for d in docs:
        key = (d.natureza_operacao or "(nao informado)").upper()[:60]
        nat[key]["n"] += 1
        nat[key]["vol"] += d.valor_total
    _hdr(ws, 1, ["Natureza de Operacao", "Qtd", "Volume (R$)", "% Volume"])
    r = 2
    for k, a in sorted(nat.items(), key=lambda kv: -kv[1]["vol"]):
        ws.cell(row=r, column=1, value=k)
        ws.cell(row=r, column=2, value=a["n"])
        ws.cell(row=r, column=3, value=round(a["vol"], 2)).number_format = _MONEY
        ws.cell(row=r, column=4, value=round(a["vol"] / total * 100, 1) if total else 0).number_format = "0.0"
        r += 1
    # CFOP por-item (distinto por documento)
    cfop_count: Counter = Counter()
    for d in docs:
        for c in (d.cfops or ([d.cfop] if d.cfop else [])):
            cfop_count[c] += 1
    r += 2
    ws.cell(row=r, column=1, value="DISTRIBUICAO POR CFOP (itens)").font = _BOLD
    r += 1
    _hdr(ws, r, ["CFOP", "Qtd documentos", "", ""])
    r += 1
    for cfop, n in cfop_count.most_common():
        ws.cell(row=r, column=1, value=cfop)
        ws.cell(row=r, column=2, value=n)
        r += 1
    _larguras(ws, {"A": 62, "B": 16, "C": 16, "D": 10})

    # ── Aba 4: Por Dia ───────────────────────────────────────────────────
    ws = wb.create_sheet("4. Por Dia")
    dia: dict[str, dict] = defaultdict(lambda: {"n": 0, "vol": 0.0})
    for d in docs:
        k = d.data_emissao or "-"
        dia[k]["n"] += 1
        dia[k]["vol"] += d.valor_total
    _hdr(ws, 1, ["Data", "Qtd", "Volume (R$)"])
    r = 2
    for k in sorted(dia):
        ws.cell(row=r, column=1, value=k)
        ws.cell(row=r, column=2, value=dia[k]["n"])
        ws.cell(row=r, column=3, value=round(dia[k]["vol"], 2)).number_format = _MONEY
        r += 1
    _larguras(ws, {"A": 14, "B": 10, "C": 16})

    # ── Aba 5: Notas (detalhe) ───────────────────────────────────────────
    ws = wb.create_sheet("5. Notas")
    _hdr(ws, 1, ["Chave", "Tipo", "Num", "Serie", "Data", "Emit CNPJ", "Emit Nome",
                 "Valor", "ICMS", "PIS", "COFINS", "CFOP", "Situacao", "Chave OK"])
    r = 2
    for d in sorted(docs, key=lambda d: (d.data_emissao, d.emit_nome or "")):
        chave_ok = "OK" if d.chave_valida else ("X" if d.chave_valida is False else "-")
        vals = [d.chave, d.tipo, d.numero, d.serie, d.data_emissao, d.emit_cnpj,
                (d.emit_nome or "")[:30], d.valor_total, d.valor_icms, d.valor_pis,
                d.valor_cofins, d.cfop, d.situacao, chave_ok]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            if c in (8, 9, 10, 11):
                cell.number_format = _MONEY
        if d.chave_valida is False or d.situacao in ("CANCELADA", "DENEGADA"):
            for c in range(1, 15):
                ws.cell(row=r, column=c).fill = _RED
        r += 1
    _larguras(ws, dict(zip("ABCDEFGHIJKLMN",
              [46, 7, 8, 6, 12, 16, 32, 14, 12, 10, 12, 12, 12, 9])))
    ws.freeze_panes = "A2"

    # ── Aba 6: Alertas ───────────────────────────────────────────────────
    ws = wb.create_sheet("6. Alertas")
    ws["A1"] = "ALERTAS — documentos que exigem atencao"
    ws["A1"].font = _TITULO
    _hdr(ws, 3, ["Tipo Alerta", "Chave", "Emitente", "Valor (R$)", "Detalhe"])
    r = 4

    def _linha_alerta(tipo, d, detalhe, fill):
        nonlocal r
        ws.cell(row=r, column=1, value=tipo).font = _BOLD
        ws.cell(row=r, column=2, value=d.chave)
        ws.cell(row=r, column=3, value=(d.emit_nome or "")[:30])
        ws.cell(row=r, column=4, value=round(d.valor_total, 2)).number_format = _MONEY
        ws.cell(row=r, column=5, value=detalhe)
        for c in range(1, 6):
            ws.cell(row=r, column=c).fill = fill
        r += 1

    for d in invalidas:
        _linha_alerta("CHAVE INVALIDA", d, "DV mod-11 nao confere", _RED)
    for d in canceladas:
        _linha_alerta(d.situacao, d, "documento sem validade fiscal", _RED)
    for d in nao_ativos:
        _linha_alerta("EMITENTE NAO-ATIVO", d, sit_cad(d.emit_cnpj), _AMBER)
    if r == 4:
        ws.cell(row=4, column=1,
                value="Nenhum alerta — todas as notas validas, ativas e nao-canceladas.").font = _BOLD
    _larguras(ws, {"A": 20, "B": 46, "C": 32, "D": 14, "E": 30})

    stats = {
        "total_documentos": len(docs),
        "volume_total": round(total, 2),
        "icms": round(icms, 2), "pis": round(pis, 2), "cofins": round(cofins, 2),
        "por_situacao": dict(por_situacao),
        "chaves_invalidas": len(invalidas),
        "canceladas": len(canceladas),
        "emitentes_nao_ativos": len(nao_ativos),
        "fornecedores": len({d.emit_cnpj for d in docs if d.emit_cnpj}),
        "periodo": (datas[0], datas[-1]) if datas else None,
    }
    return wb, stats


# ─────────────────────────────────────────────────────────────────────────────
# Versão HTML (e, via Playwright, PDF) — mesmos dados do XLSX
# ─────────────────────────────────────────────────────────────────────────────

def _money(x: float) -> str:
    return "R$ " + format(x or 0.0, ",.2f")


def gerar_laudo_notas_html(
    documentos: Iterable[DocumentoFiscalLido],
    situacao_por_cnpj: Optional[dict[str, str]] = None,
) -> tuple[str, dict]:
    """Versão HTML do laudo de notas (mesmos números do XLSX). Retorna (html, stats)."""
    docs = [d for d in documentos if d.chave]
    sit_map = situacao_por_cnpj or {}

    def sit_cad(cnpj: str) -> str:
        return (sit_map.get(cnpj) or sit_map.get(cnpj[:8], "")) if cnpj else ""

    total = sum(d.valor_total for d in docs)
    icms = sum(d.valor_icms for d in docs)
    pis = sum(d.valor_pis for d in docs)
    cofins = sum(d.valor_cofins for d in docs)
    por_situacao = Counter(d.situacao for d in docs)
    invalidas = [d for d in docs if d.chave_valida is False]
    canceladas = [d for d in docs if d.situacao in ("CANCELADA", "DENEGADA")]
    nao_ativos = [d for d in docs if _situacao_nao_ativa(sit_cad(d.emit_cnpj))]
    datas = sorted(d.data_emissao for d in docs if d.data_emissao)
    tipos = Counter(d.tipo for d in docs)

    agg: dict[str, dict] = defaultdict(lambda: {"n": 0, "vol": 0.0, "nome": ""})
    for d in docs:
        a = agg[d.emit_cnpj]
        a["n"] += 1
        a["vol"] += d.valor_total
        a["nome"] = d.emit_nome or a["nome"]
    top_forn = sorted(agg.items(), key=lambda kv: -kv[1]["vol"])[:25]

    nat: dict[str, dict] = defaultdict(lambda: {"n": 0, "vol": 0.0})
    for d in docs:
        k = (d.natureza_operacao or "(nao informado)").upper()[:50]
        nat[k]["n"] += 1
        nat[k]["vol"] += d.valor_total
    top_nat = sorted(nat.items(), key=lambda kv: -kv[1]["vol"])[:10]

    cfop_count: Counter = Counter()
    for d in docs:
        for c in (d.cfops or ([d.cfop] if d.cfop else [])):
            cfop_count[c] += 1

    e = _html.escape
    periodo = (datas[0] + " a " + datas[-1]) if datas else "-"
    n_alertas = len(invalidas) + len(canceladas) + len(nao_ativos)

    css = """
@page{size:A4;margin:14mm}
*{box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;color:#1b2733;font-size:10pt;margin:0;line-height:1.5}
.hd{background:#0F172A;color:#fff;padding:20px 28px}
.hd h1{margin:0;font-size:19pt}
.hd .sub{opacity:.85;font-size:8.5pt;text-transform:uppercase;letter-spacing:.14em;margin-top:5px}
.kpi{display:inline-block;margin:10px 22px 10px 0}
.kpi b{display:block;font-size:16pt;color:#0F172A}
.kpibox{padding:14px 28px}
.alert{background:#FDE2E2;color:#9B1C1C}
.ok{background:#DCFCE7;color:#166534}
.badge{display:inline-block;padding:3px 12px;border-radius:12px;font-size:9pt;font-weight:600}
h2{font-size:12.5pt;color:#12345e;margin:20px 28px 6px;padding:3px 0 3px 10px;border-left:3px solid #1f7fb8}
table{width:calc(100% - 56px);margin:8px 28px;border-collapse:collapse;font-size:9pt}
th{background:#0F172A;color:#fff;padding:7px 9px;text-align:left}
td{padding:6px 9px;border-bottom:1px solid #E2E8F0}
td.n{text-align:right}
tr.crit td{background:#FDE2E2}
.foot{margin:18px 28px;font-size:8pt;color:#64748b;border-top:1px solid #E2E8F0;padding-top:8px}
"""

    def linhas_forn():
        out = []
        for cnpj, a in top_forn:
            sc = sit_cad(cnpj)
            cls = " class='crit'" if _situacao_nao_ativa(sc) else ""
            out.append(
                "<tr" + cls + "><td>" + e(cnpj) + "</td><td>" + e((a["nome"] or "")[:38])
                + "</td><td class='n'>" + str(a["n"]) + "</td><td class='n'>" + _money(a["vol"])
                + "</td><td>" + e(sc or "(sem cadastro)") + "</td></tr>")
        return "".join(out)

    def linhas_nat():
        return "".join(
            "<tr><td>" + e(k) + "</td><td class='n'>" + str(a["n"]) + "</td><td class='n'>"
            + _money(a["vol"]) + "</td><td class='n'>"
            + format((a["vol"] / total * 100) if total else 0, ".1f") + "%</td></tr>"
            for k, a in top_nat)

    def linhas_cfop():
        return "".join(
            "<tr><td>" + e(c) + "</td><td class='n'>" + str(n) + "</td></tr>"
            for c, n in cfop_count.most_common(12))

    def bloco_alertas():
        if n_alertas == 0:
            return ("<p style='margin:8px 28px' class='badge ok'>Nenhum alerta — "
                    "todas as notas validas, ativas e nao-canceladas.</p>")
        linhas = []
        for d in invalidas[:50]:
            linhas.append("<tr class='crit'><td>CHAVE INVALIDA</td><td>" + e(d.chave)
                          + "</td><td>" + e((d.emit_nome or "")[:30]) + "</td><td class='n'>"
                          + _money(d.valor_total) + "</td></tr>")
        for d in canceladas[:50]:
            linhas.append("<tr class='crit'><td>" + e(d.situacao) + "</td><td>" + e(d.chave)
                          + "</td><td>" + e((d.emit_nome or "")[:30]) + "</td><td class='n'>"
                          + _money(d.valor_total) + "</td></tr>")
        for d in nao_ativos[:50]:
            linhas.append("<tr><td>EMITENTE NAO-ATIVO</td><td>" + e(d.chave)
                          + "</td><td>" + e((d.emit_nome or "")[:30]) + "</td><td class='n'>"
                          + _money(d.valor_total) + "</td></tr>")
        return ("<table><tr><th>Alerta</th><th>Chave</th><th>Emitente</th><th>Valor</th></tr>"
                + "".join(linhas) + "</table>")

    html = (
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'><style>" + css + "</style></head><body>"
        "<div class='hd'><h1>Laudo de Documentos Fiscais</h1>"
        "<div class='sub'>ORGATEC &middot; Contabilidade &middot; Auditoria &middot; Compliance</div>"
        "<div style='margin-top:7px'>Periodo " + e(periodo) + " &middot; "
        + str(len(docs)) + " documentos</div></div>"
        "<div class='kpibox'>"
        "<div class='kpi'><b>" + format(len(docs), ",") + "</b>documentos ("
        + ", ".join(t + " " + str(n) for t, n in tipos.items()) + ")</div>"
        "<div class='kpi'><b>" + _money(total) + "</b>volume documentado</div>"
        "<div class='kpi'><b>" + str(len({d.emit_cnpj for d in docs if d.emit_cnpj})) + "</b>fornecedores</div>"
        "<div class='kpi'><b>" + _money(icms) + "</b>ICMS</div>"
        "<div class='kpi'><b>" + str(por_situacao.get("CANCELADA", 0) + por_situacao.get("DENEGADA", 0))
        + "</b>canceladas/denegadas</div>"
        "<div class='kpi'><span class='badge " + ("alert" if n_alertas else "ok") + "'>"
        + str(n_alertas) + " alertas</span></div>"
        "</div>"
        "<h2>Top Fornecedores (por volume)</h2>"
        "<table><tr><th>CNPJ</th><th>Razao Social</th><th>Qtd</th><th>Volume</th>"
        "<th>Situacao Cadastral</th></tr>" + linhas_forn() + "</table>"
        "<h2>Natureza de Operacao</h2>"
        "<table><tr><th>Natureza</th><th>Qtd</th><th>Volume</th><th>%</th></tr>" + linhas_nat() + "</table>"
        "<h2>Distribuicao por CFOP</h2>"
        "<table><tr><th>CFOP</th><th>Qtd documentos</th></tr>" + linhas_cfop() + "</table>"
        "<h2>Alertas</h2>" + bloco_alertas()
        + "<div class='foot'>Validacao de chave estrutural (mod-11) — nao prova autenticidade "
        "(exige SEFAZ). Documentos cancelados/denegados excluidos da cobertura. "
        "Detalhe documento-a-documento disponivel no formato XLSX.</div>"
        "</body></html>"
    )

    stats = {
        "total_documentos": len(docs),
        "volume_total": round(total, 2),
        "fornecedores": len({d.emit_cnpj for d in docs if d.emit_cnpj}),
        "chaves_invalidas": len(invalidas),
        "canceladas": len(canceladas),
    }
    return html, stats
