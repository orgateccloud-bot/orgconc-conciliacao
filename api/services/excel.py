"""Geracao de planilha XLSX com 4 abas (Resumo, Transacoes, Anomalias, Evolucao Diaria)."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from api.parsers import _classificar, _top_categorias_e_contrapartes

_LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "static" / "logo.png"


def _xlsx_estilos() -> dict:
    """Paleta de cores, fontes e bordas compartilhados entre as abas XLSX."""
    BLUE_DARK = "0A3A7A"; BLUE = "1E6FD9"; WHITE = "FFFFFF"
    GRAY_BORDER = "E2E8F0"; GRAY_LIGHT = "F7FAFC"; GRAY_HOVER = "EFF6FF"
    RED = "DC2626"; RED_BG = "FEE2E2"
    ORANGE = "EA580C"; ORANGE_BG = "FFEDD5"
    YELLOW = "CA8A04"; YELLOW_BG = "FEF9C3"
    GREEN = "16A34A"
    TOTAL_BG = "374151"
    ANOMALIA_FILL = "FFE4B5"
    ANOMALIA_FONT = "D97706"
    side_thin = Side(border_style="thin", color=GRAY_BORDER)
    return dict(
        BLUE_DARK=BLUE_DARK, BLUE=BLUE, WHITE=WHITE,
        RED=RED, ORANGE=ORANGE, YELLOW=YELLOW, GREEN=GREEN,
        TOTAL_BG=TOTAL_BG, ANOMALIA_FILL=ANOMALIA_FILL, ANOMALIA_FONT=ANOMALIA_FONT,
        fill_blue_dark=PatternFill("solid", fgColor=BLUE_DARK),
        fill_blue=PatternFill("solid", fgColor=BLUE),
        fill_zebra=PatternFill("solid", fgColor=GRAY_LIGHT),
        fill_kpi_blue=PatternFill("solid", fgColor=GRAY_HOVER),
        fill_critico=PatternFill("solid", fgColor=RED_BG),
        fill_alerta=PatternFill("solid", fgColor=ORANGE_BG),
        fill_atencao=PatternFill("solid", fgColor=YELLOW_BG),
        fill_total=PatternFill("solid", fgColor=TOTAL_BG),
        fill_anomalia=PatternFill("solid", fgColor=ANOMALIA_FILL),
        font_h_white=Font(bold=True, color=WHITE, size=11, name="Calibri"),
        font_brand=Font(bold=True, size=24, color=BLUE_DARK, name="Calibri"),
        font_brand_sub=Font(color=BLUE, size=10, italic=True, name="Calibri"),
        font_section=Font(bold=True, size=13, color=BLUE_DARK, name="Calibri"),
        font_kpi_lbl=Font(bold=True, size=9, color="64748B", name="Calibri"),
        font_kpi_val_red=Font(bold=True, size=22, color=RED, name="Calibri"),
        font_kpi_val_orange=Font(bold=True, size=22, color=ORANGE, name="Calibri"),
        font_kpi_val_yellow=Font(bold=True, size=22, color=YELLOW, name="Calibri"),
        font_kpi_val_blue=Font(bold=True, size=22, color=BLUE_DARK, name="Calibri"),
        font_total=Font(bold=True, color=WHITE, name="Calibri", size=10),
        font_anomalia=Font(bold=True, color=ANOMALIA_FONT, name="Calibri", size=10),
        side_thin=side_thin,
        border_all=Border(left=side_thin, right=side_thin, top=side_thin, bottom=side_thin),
        border_kpi=Border(left=side_thin, right=side_thin,
                          top=Side(border_style="medium", color=BLUE), bottom=side_thin),
        FMT_BRL='R$ #,##0.00;[Red]-R$ #,##0.00',
        FMT_BRL_POS='R$ #,##0.00',
    )


def _xlsx_aba_resumo(ws, extratos: list[dict], anomalias: list[dict], e: dict) -> None:
    """Preenche a aba Resumo com cabecalho, KPIs e tabelas."""
    ws.title = "Resumo"
    ws.sheet_view.showGridLines = False

    def estilo_header(cells, fill=None, font=None):
        fill = fill or e["fill_blue_dark"]
        font = font or e["font_h_white"]
        for c in cells:
            c.fill = fill; c.font = font
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.border = e["border_all"]

    def linha_borda(ws_inner, row, cols):
        for c in range(1, cols + 1):
            ws_inner.cell(row=row, column=c).border = e["border_all"]

    if _LOGO_PATH.exists():
        try:
            img = XLImage(str(_LOGO_PATH))
            img.width = 64; img.height = 64
            ws.add_image(img, "A1")
        except Exception:
            pass
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 24
    ws.row_dimensions[3].height = 10

    ws["B1"] = "ORGATEC"
    ws["B1"].font = e["font_brand"]
    ws["B2"] = "Contabilidade & Auditoria"
    ws["B2"].font = e["font_brand_sub"]
    ws.merge_cells("B1:E1"); ws.merge_cells("B2:E2")

    ws["F1"] = "RELATÓRIO DE CONCILIAÇÃO"
    ws["F1"].font = Font(bold=True, color=e["BLUE_DARK"], size=11, name="Calibri")
    ws["F1"].alignment = Alignment(horizontal="right", vertical="bottom")
    ws.merge_cells("F1:H1")
    ws["F2"] = f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["F2"].font = Font(italic=True, color="64748B", size=10, name="Calibri")
    ws["F2"].alignment = Alignment(horizontal="right", vertical="top")
    ws.merge_cells("F2:H2")

    for col in range(1, 9):
        ws.cell(row=3, column=col).fill = e["fill_blue"]
    ws.row_dimensions[3].height = 4

    # ── MELHORIA 5: Período ──────────────────────────────────────────────────
    todas_tx = [t for ex in extratos for t in ex["transacoes"]]
    if todas_tx:
        datas = [t["data"] for t in todas_tx if t.get("data")]
        if datas:
            try:
                # datas podem ser strings "YYYY-MM-DD" ou objetos date/datetime
                def _parse_data(d):
                    if hasattr(d, "strftime"):
                        return d
                    return datetime.strptime(str(d)[:10], "%Y-%m-%d")
                datas_dt = [_parse_data(d) for d in datas]
                dt_min = min(datas_dt).strftime("%d/%m/%Y")
                dt_max = max(datas_dt).strftime("%d/%m/%Y")
                ws.cell(row=4, column=1, value="Período:").font = Font(
                    bold=True, color=e["BLUE_DARK"], size=10, name="Calibri")
                periodo_cell = ws.cell(row=4, column=2, value=f"{dt_min} a {dt_max}")
                periodo_cell.font = Font(color="64748B", size=10, name="Calibri")
                ws.merge_cells("B4:E4")
                ws.row_dimensions[4].height = 16
            except Exception:
                pass

    ws.cell(row=5, column=1, value="VISÃO GERAL").font = e["font_section"]
    ws.merge_cells("A5:H5")

    total_tx   = sum(ex["qtd"] for ex in extratos)
    total_cred = sum(t["valor"] for ex in extratos for t in ex["transacoes"] if t["valor"] > 0)
    total_deb  = sum(t["valor"] for ex in extratos for t in ex["transacoes"] if t["valor"] < 0)
    saldo = total_cred + total_deb

    sev_count = {"critico": 0, "alerta": 0, "atencao": 0}
    for a in anomalias:
        sev_count[a["severidade"]] = sev_count.get(a["severidade"], 0) + 1

    kpis = [
        ("TRANSAÇÕES",  total_tx,   e["font_kpi_val_blue"], e["fill_kpi_blue"], None),
        ("CRÉDITOS",    total_cred,
         Font(bold=True, size=18, color=e["GREEN"], name="Calibri"),
         e["fill_kpi_blue"], e["FMT_BRL_POS"]),
        ("DÉBITOS",     total_deb,
         Font(bold=True, size=18, color=e["RED"], name="Calibri"),
         e["fill_kpi_blue"], e["FMT_BRL"]),
        ("SALDO",       saldo,
         Font(bold=True, size=18, color=e["BLUE_DARK"], name="Calibri"),
         e["fill_kpi_blue"], e["FMT_BRL"]),
    ]
    sev_kpis = [
        ("🔴 CRÍTICAS", sev_count["critico"], e["font_kpi_val_red"],    e["fill_critico"]),
        ("🟠 ALERTAS",  sev_count["alerta"],  e["font_kpi_val_orange"], e["fill_alerta"]),
        ("🟡 ATENÇÃO",  sev_count["atencao"], e["font_kpi_val_yellow"], e["fill_atencao"]),
        ("✅ TOTAL",    len(anomalias),        e["font_kpi_val_blue"],   e["fill_kpi_blue"]),
    ]

    border_kpi_bottom = Border(left=e["side_thin"], right=e["side_thin"], bottom=e["side_thin"])

    def aplicar_kpi(ws_inner, row_lbl, row_val, col, label, val, font_val, fill, fmt=None):
        lbl = ws_inner.cell(row=row_lbl, column=col, value=label)
        lbl.font = e["font_kpi_lbl"]
        lbl.alignment = Alignment(horizontal="left", vertical="bottom")
        lbl.fill = fill; lbl.border = e["border_kpi"]
        v = ws_inner.cell(row=row_val, column=col, value=val)
        v.font = font_val
        v.alignment = Alignment(horizontal="left", vertical="center")
        v.fill = fill; v.border = border_kpi_bottom
        if fmt:
            v.number_format = fmt
        lbl2 = ws_inner.cell(row=row_lbl, column=col + 1)
        lbl2.fill = fill; lbl2.border = e["border_kpi"]
        v2 = ws_inner.cell(row=row_val, column=col + 1)
        v2.fill = fill; v2.border = border_kpi_bottom
        ws_inner.merge_cells(start_row=row_lbl, start_column=col, end_row=row_lbl, end_column=col + 1)
        ws_inner.merge_cells(start_row=row_val, start_column=col, end_row=row_val, end_column=col + 1)

    for i, (label, val, font_val, fill, fmt) in enumerate(kpis):
        aplicar_kpi(ws, 6, 7, 1 + i * 2, label, val, font_val, fill, fmt)
    ws.row_dimensions[6].height = 18
    ws.row_dimensions[7].height = 30

    for i, (label, val, font_val, fill) in enumerate(sev_kpis):
        aplicar_kpi(ws, 9, 10, 1 + i * 2, label, val, font_val, fill)
    ws.row_dimensions[9].height = 18
    ws.row_dimensions[10].height = 30

    r = 12
    ws.cell(row=r, column=1, value="MOVIMENTAÇÃO POR CONTA").font = e["font_section"]
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    r += 1
    headers_conta = ["Conta", "Arquivo", "Transações", "Créditos", "Débitos", "Saldo", "% do Total"]
    for col, txt in enumerate(headers_conta, 1):
        ws.cell(row=r, column=col, value=txt)
    estilo_header([ws.cell(row=r, column=c) for c in range(1, len(headers_conta) + 1)])
    ws.row_dimensions[r].height = 24
    r += 1
    for i, ex in enumerate(extratos):
        cred = sum(t["valor"] for t in ex["transacoes"] if t["valor"] > 0)
        deb  = sum(t["valor"] for t in ex["transacoes"] if t["valor"] < 0)
        sld  = cred + deb
        vol_e = cred + abs(deb)
        vol_total_contas = sum(
            sum(t["valor"] for t in ex2["transacoes"] if t["valor"] > 0)
            + abs(sum(t["valor"] for t in ex2["transacoes"] if t["valor"] < 0))
            for ex2 in extratos
        ) or 1
        pct = vol_e / vol_total_contas
        ws.cell(row=r, column=1, value=ex["conta"])
        ws.cell(row=r, column=2, value=ex["arquivo"])
        ws.cell(row=r, column=3, value=ex["qtd"])
        c = ws.cell(row=r, column=4, value=cred)
        c.number_format = e["FMT_BRL_POS"]; c.font = Font(color=e["GREEN"], name="Calibri")
        c = ws.cell(row=r, column=5, value=deb)
        c.number_format = e["FMT_BRL"];     c.font = Font(color=e["RED"], name="Calibri")
        c = ws.cell(row=r, column=6, value=sld)
        c.number_format = e["FMT_BRL"];     c.font = Font(bold=True, name="Calibri")
        c = ws.cell(row=r, column=7, value=pct); c.number_format = '0.0%'
        if i % 2 == 1:
            for col in range(1, len(headers_conta) + 1):
                ws.cell(row=r, column=col).fill = e["fill_zebra"]
        linha_borda(ws, r, len(headers_conta))
        ws.row_dimensions[r].height = 22
        r += 1

    stats = _top_categorias_e_contrapartes(extratos)
    cats = stats["cats"]
    if cats:
        r += 2
        ws.cell(row=r, column=1, value="🏷 DISTRIBUIÇÃO POR CATEGORIA").font = e["font_section"]
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        r += 1
        for col, txt in enumerate(["Categoria", "Qtd", "Valor Total", "Ticket Médio", "% Volume", "", "", ""], 1):
            if txt:
                ws.cell(row=r, column=col, value=txt)
        estilo_header([ws.cell(row=r, column=c) for c in range(1, 6)],
                      fill=e["fill_blue"], font=e["font_h_white"])
        ws.row_dimensions[r].height = 22
        r += 1
        vol_total = sum(abs(d["valor"]) for d in cats.values()) or 1
        for i, cat in enumerate(sorted(cats, key=lambda k: -abs(cats[k]["valor"]))):
            d = cats[cat]
            tk = d["valor"] / d["qtd"] if d["qtd"] else 0
            pct = abs(d["valor"]) / vol_total
            ws.cell(row=r, column=1, value=cat)
            ws.cell(row=r, column=2, value=d["qtd"])
            c = ws.cell(row=r, column=3, value=d["valor"]); c.number_format = e["FMT_BRL"]
            c.font = Font(color=e["GREEN"] if d["valor"] > 0 else e["RED"], name="Calibri")
            c = ws.cell(row=r, column=4, value=tk); c.number_format = e["FMT_BRL"]
            c = ws.cell(row=r, column=5, value=pct); c.number_format = '0.0%'
            if i % 2 == 1:
                for col in range(1, 6):
                    ws.cell(row=r, column=col).fill = e["fill_zebra"]
            for col in range(1, 6):
                ws.cell(row=r, column=col).border = e["border_all"]
            r += 1

    top_cps = sorted(stats["contrapartes"].items(), key=lambda x: -abs(x[1]["valor"]))[:10]
    if top_cps:
        r += 2
        ws.cell(row=r, column=1, value="🏆 TOP 10 CONTRAPARTES").font = e["font_section"]
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        r += 1
        for col, txt in enumerate(["#", "Contraparte (CNPJ/CPF/Nome)", "Transações", "Volume", "Tipo"], 1):
            ws.cell(row=r, column=col, value=txt)
        estilo_header([ws.cell(row=r, column=c) for c in range(1, 6)],
                      fill=e["fill_blue"], font=e["font_h_white"])
        ws.row_dimensions[r].height = 22
        r += 1
        for i, (chave, d) in enumerate(top_cps, 1):
            ws.cell(row=r, column=1, value=i)
            ws.cell(row=r, column=2, value=chave)
            ws.cell(row=r, column=3, value=d["qtd"])
            c = ws.cell(row=r, column=4, value=d["valor"]); c.number_format = e["FMT_BRL"]
            c.font = Font(color=e["GREEN"] if d["valor"] > 0 else e["RED"], bold=True, name="Calibri")
            ws.cell(row=r, column=5, value="Recebimento" if d["valor"] > 0 else "Pagamento")
            if i % 2 == 0:
                for col in range(1, 6):
                    ws.cell(row=r, column=col).fill = e["fill_zebra"]
            for col in range(1, 6):
                ws.cell(row=r, column=col).border = e["border_all"]
            r += 1

    crit_lista = [a for a in anomalias if a["severidade"] == "critico"][:10]
    if crit_lista:
        r += 2
        ws.cell(row=r, column=1, value="🔴 ACHADOS CRÍTICOS").font = e["font_section"]
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        r += 1
        for col, txt in enumerate(["Tipo", "Título", "Conta", "Valor", "Detalhe"], 1):
            ws.cell(row=r, column=col, value=txt)
        estilo_header([ws.cell(row=r, column=c) for c in range(1, 6)],
                      fill=e["fill_blue"], font=e["font_h_white"])
        ws.row_dimensions[r].height = 22
        r += 1
        for a in crit_lista:
            ws.cell(row=r, column=1, value=a["tipo"])
            ws.cell(row=r, column=2, value=a["titulo"])
            ws.cell(row=r, column=3, value=a["conta"])
            c = ws.cell(row=r, column=4, value=a.get("valor", 0)); c.number_format = e["FMT_BRL"]
            ws.cell(row=r, column=5, value=a["detalhe"])
            for col in range(1, 6):
                ws.cell(row=r, column=col).fill = e["fill_critico"]
                ws.cell(row=r, column=col).border = e["border_all"]
            r += 1

    for col, w in zip("ABCDEFGH", [26, 32, 13, 16, 16, 16, 13, 8]):
        ws.column_dimensions[col].width = w

    # ── MELHORIA 6: Proteção da aba Resumo ───────────────────────────────────
    ws.protection.sheet = True


def _xlsx_aba_transacoes(wb, extratos: list[dict], anomalias: list[dict], e: dict) -> None:
    """Cria e preenche a aba Transacoes com Categoria, Anomalia e linha de totais."""
    ws = wb.create_sheet("Transações")
    ws.sheet_view.showGridLines = False
    ws.row_dimensions[1].height = 30

    # ── MELHORIA 1 e 2: colunas Categoria e Anomalia ─────────────────────────
    # Colunas: Conta | Data | Tipo | Categoria | Valor | Memo | Nome | Doc | Anomalia
    cabec = ["Conta", "Data", "Tipo", "Categoria", "Valor", "Memo", "Nome", "Doc", "Anomalia"]
    COL_CONTA = 1; COL_DATA = 2; COL_TIPO = 3; COL_CAT = 4; COL_VALOR = 5
    COL_MEMO = 6; COL_NOME = 7; COL_DOC = 8; COL_ANOMALIA = 9

    for col, txt in enumerate(cabec, 1):
        cell = ws.cell(row=1, column=col, value=txt)
        cell.fill = e["fill_blue_dark"]
        cell.font = e["font_h_white"]
        cell.alignment = Alignment(horizontal="left", vertical="center")
        cell.border = e["border_all"]

    # Construir set de chaves anômalas (data, valor) para lookup rápido
    chaves_anomalas: set[tuple] = set()
    for a in anomalias:
        if a.get("data") and a.get("valor") is not None:
            chaves_anomalas.add((str(a["data"])[:10], float(a["valor"])))

    r = 2
    for ex in extratos:
        for t in ex["transacoes"]:
            ws.cell(row=r, column=COL_CONTA, value=ex["conta"])
            ws.cell(row=r, column=COL_DATA,  value=t["data"])

            tipo_cell = ws.cell(row=r, column=COL_TIPO, value=t["tipo"])
            if t["tipo"] == "CREDIT":
                tipo_cell.font = Font(color=e["GREEN"], bold=True, name="Calibri", size=10)
            elif t["tipo"] == "DEBIT":
                tipo_cell.font = Font(color=e["RED"], bold=True, name="Calibri", size=10)

            # Melhoria 1: Categoria
            cat = _classificar(t.get("memo", ""), t.get("nome", ""))
            ws.cell(row=r, column=COL_CAT, value=cat)

            c = ws.cell(row=r, column=COL_VALOR, value=t["valor"])
            c.number_format = e["FMT_BRL"]
            c.font = Font(color=e["GREEN"] if t["valor"] > 0 else e["RED"],
                          name="Calibri", size=10, bold=True)

            ws.cell(row=r, column=COL_MEMO, value=t["memo"])
            ws.cell(row=r, column=COL_NOME, value=t["nome"])
            ws.cell(row=r, column=COL_DOC,  value=t["checknum"])

            # Melhoria 2: Anomalia — cruza por (data, valor)
            data_str = str(t.get("data", ""))[:10]
            eh_anomalia = (data_str, float(t["valor"])) in chaves_anomalas
            anom_cell = ws.cell(row=r, column=COL_ANOMALIA, value="Sim" if eh_anomalia else "Não")
            if eh_anomalia:
                anom_cell.fill = e["fill_anomalia"]
                anom_cell.font = e["font_anomalia"]

            if r % 2 == 0:
                for col in range(1, len(cabec) + 1):
                    if col not in (COL_TIPO, COL_VALOR, COL_ANOMALIA) or not eh_anomalia:
                        if col not in (COL_TIPO, COL_VALOR):
                            ws.cell(row=r, column=col).fill = e["fill_zebra"]

            for col in range(1, len(cabec) + 1):
                ws.cell(row=r, column=col).border = e["border_all"]
            r += 1

    # ── MELHORIA 3: Linha de totais ───────────────────────────────────────────
    ultima_linha_dados = r - 1
    total_valor = sum(t["valor"] for ex in extratos for t in ex["transacoes"])

    # Célula TOTAL na coluna Conta
    tot_conta = ws.cell(row=r, column=COL_CONTA, value="TOTAL")
    tot_conta.fill = e["fill_total"]
    tot_conta.font = e["font_total"]
    tot_conta.border = e["border_all"]

    # Soma na coluna Valor (valor calculado diretamente)
    tot_val = ws.cell(row=r, column=COL_VALOR, value=total_valor)
    tot_val.fill = e["fill_total"]
    tot_val.font = Font(bold=True, color=e["WHITE"], name="Calibri", size=10)
    tot_val.number_format = e["FMT_BRL"]
    tot_val.border = e["border_all"]

    # Demais colunas da linha de totais — apenas fundo e borda
    for col in range(1, len(cabec) + 1):
        cell = ws.cell(row=r, column=col)
        if cell.value is None:
            cell.fill = e["fill_total"]
            cell.border = e["border_all"]
    ws.row_dimensions[r].height = 24
    r += 1

    # ── Larguras das colunas ──────────────────────────────────────────────────
    # A=Conta, B=Data, C=Tipo, D=Categoria, E=Valor, F=Memo, G=Nome, H=Doc, I=Anomalia
    for col_letter, w in zip("ABCDEFGHI", [26, 12, 10, 22, 16, 52, 30, 14, 10]):
        ws.column_dimensions[col_letter].width = w

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cabec))}{ultima_linha_dados}"


def _xlsx_aba_anomalias(wb, anomalias: list[dict], e: dict) -> None:
    """Cria e preenche a aba Anomalias."""
    ws = wb.create_sheet("Anomalias")
    ws.sheet_view.showGridLines = False
    ws.row_dimensions[1].height = 30
    cabec = ["Severidade", "Tipo", "Título", "Conta", "Valor", "Detalhe"]
    for col, txt in enumerate(cabec, 1):
        cell = ws.cell(row=1, column=col, value=txt)
        cell.fill = e["fill_blue_dark"]
        cell.font = e["font_h_white"]
        cell.alignment = Alignment(horizontal="left", vertical="center")
        cell.border = e["border_all"]
    r = 2
    sev_meta = {
        "critico": ("🔴 CRÍTICO", e["fill_critico"],
                    Font(bold=True, color=e["RED"],    name="Calibri", size=10)),
        "alerta":  ("🟠 ALERTA",  e["fill_alerta"],
                    Font(bold=True, color=e["ORANGE"], name="Calibri", size=10)),
        "atencao": ("🟡 ATENÇÃO", e["fill_atencao"],
                    Font(bold=True, color=e["YELLOW"], name="Calibri", size=10)),
    }
    for a in anomalias:
        label, fill, font_sev = sev_meta.get(a["severidade"], ("?", None, None))
        sev_cell = ws.cell(row=r, column=1, value=label)
        if font_sev:
            sev_cell.font = font_sev
        ws.cell(row=r, column=2, value=a["tipo"])
        ws.cell(row=r, column=3, value=a["titulo"])
        ws.cell(row=r, column=4, value=a["conta"])
        c = ws.cell(row=r, column=5, value=a.get("valor", 0))
        c.number_format = e["FMT_BRL"]
        ws.cell(row=r, column=6, value=a["detalhe"])
        if fill:
            for col in range(1, len(cabec) + 1):
                ws.cell(row=r, column=col).fill = fill
        for col in range(1, len(cabec) + 1):
            ws.cell(row=r, column=col).border = e["border_all"]
        r += 1
    for col, w in zip("ABCDEF", [15, 22, 42, 28, 16, 60]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    if r > 2:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cabec))}{r-1}"

    # ── MELHORIA 6: Proteção da aba Anomalias ────────────────────────────────
    ws.protection.sheet = True


def _xlsx_aba_evolucao_diaria(wb, extratos: list[dict], e: dict) -> None:
    """Cria a 4ª aba 'Evolução Diária' com totais por data."""
    ws = wb.create_sheet("Evolução Diária")
    ws.sheet_view.showGridLines = False
    ws.row_dimensions[1].height = 30

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    cabec = ["Data", "Créditos (R$)", "Débitos (R$)", "Saldo do Dia"]
    for col, txt in enumerate(cabec, 1):
        cell = ws.cell(row=1, column=col, value=txt)
        cell.fill = e["fill_blue_dark"]
        cell.font = e["font_h_white"]
        cell.alignment = Alignment(horizontal="left", vertical="center")
        cell.border = e["border_all"]

    # ── Obter evolução diária via _top_categorias_e_contrapartes ─────────────
    stats = _top_categorias_e_contrapartes(extratos)
    diario = stats.get("diario", {})

    # Ordenar por data
    try:
        datas_sorted = sorted(diario.keys(), key=lambda d: str(d)[:10])
    except Exception:
        datas_sorted = sorted(diario.keys())

    r = 2
    total_cred = 0.0; total_deb = 0.0

    for i, data in enumerate(datas_sorted):
        vals = diario[data]
        cred = vals.get("cred", 0.0)
        deb  = vals.get("deb", 0.0)
        saldo_dia = cred + deb
        total_cred += cred
        total_deb  += deb

        ws.cell(row=r, column=1, value=str(data)[:10])

        c = ws.cell(row=r, column=2, value=cred)
        c.number_format = e["FMT_BRL_POS"]
        c.font = Font(color=e["GREEN"], name="Calibri", size=10)

        c = ws.cell(row=r, column=3, value=deb)
        c.number_format = e["FMT_BRL"]
        c.font = Font(color=e["RED"], name="Calibri", size=10)

        c = ws.cell(row=r, column=4, value=saldo_dia)
        c.number_format = e["FMT_BRL"]
        c.font = Font(
            color=e["GREEN"] if saldo_dia >= 0 else e["RED"],
            bold=True, name="Calibri", size=10
        )

        if i % 2 == 1:
            for col in range(1, 5):
                ws.cell(row=r, column=col).fill = e["fill_zebra"]

        for col in range(1, 5):
            ws.cell(row=r, column=col).border = e["border_all"]
        ws.row_dimensions[r].height = 20
        r += 1

    # ── Linha de totais ───────────────────────────────────────────────────────
    saldo_total = total_cred + total_deb

    tot_data = ws.cell(row=r, column=1, value="TOTAL")
    tot_data.fill = e["fill_total"]; tot_data.font = e["font_total"]
    tot_data.border = e["border_all"]

    tot_c = ws.cell(row=r, column=2, value=total_cred)
    tot_c.fill = e["fill_total"]; tot_c.font = e["font_total"]
    tot_c.number_format = e["FMT_BRL_POS"]; tot_c.border = e["border_all"]

    tot_d = ws.cell(row=r, column=3, value=total_deb)
    tot_d.fill = e["fill_total"]; tot_d.font = e["font_total"]
    tot_d.number_format = e["FMT_BRL"]; tot_d.border = e["border_all"]

    tot_s = ws.cell(row=r, column=4, value=saldo_total)
    tot_s.fill = e["fill_total"]; tot_s.font = e["font_total"]
    tot_s.number_format = e["FMT_BRL"]; tot_s.border = e["border_all"]
    ws.row_dimensions[r].height = 24
    r += 1

    # ── Larguras e controles ──────────────────────────────────────────────────
    for col_letter, w in zip("ABCD", [14, 18, 18, 18]):
        ws.column_dimensions[col_letter].width = w

    ws.freeze_panes = "A2"
    if r > 2:
        ws.auto_filter.ref = f"A1:D{r-2}"


def _gerar_xlsx(extratos: list[dict], anomalias: list[dict]) -> bytes:
    """Gera planilha XLSX com 4 abas estilizadas: Resumo, Transacoes, Anomalias, Evolucao Diaria."""
    wb = Workbook()
    e = _xlsx_estilos()
    _xlsx_aba_resumo(wb.active, extratos, anomalias, e)
    _xlsx_aba_transacoes(wb, extratos, anomalias, e)
    _xlsx_aba_anomalias(wb, anomalias, e)
    _xlsx_aba_evolucao_diaria(wb, extratos, e)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
