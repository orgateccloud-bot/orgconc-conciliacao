"""Apresentacao executiva 1-pagina - LOCAR TRANSPORTE DE BOVINOS LTDA.

Documento sintetico para apresentacao ao cliente com:
- Logo ORGATEC e identificacao
- KPIs em cards visuais
- 5 achados criticos em cores
- Proximos passos com prazos
- Layout A4 portrait, 1 pagina

Saida: PDF + HTML (compactos)
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _logo_helper import html_logo_inline

OUT_BASE = r"C:\Users\Veloso\Downloads\APRESENTACAO_EXECUTIVA_LOCAR"
OUT_HTML = Path(f"{OUT_BASE}.html")
OUT_PDF = Path(f"{OUT_BASE}.pdf")


def gerar_html():
    agora = datetime.now().strftime("%d/%m/%Y")
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Apresentacao Executiva - LOCAR TRANSPORTE DE BOVINOS LTDA</title>
<style>
@page {{
  size: A4 portrait;
  margin: 8mm 10mm 8mm 10mm;
  @bottom-right {{ content: "ORGATEC · {agora}"; font-size: 8px; color: #6B7280; }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Segoe UI', 'DejaVu Sans', Arial, sans-serif;
  color: #1a202c;
  font-size: 9pt;
  line-height: 1.4;
  background: white;
}}

/* Header com logo */
.header {{
  background: linear-gradient(135deg, #0F172A 0%, #0B1B3D 45%, #0052FF 100%);
  color: #fff;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 18px;
  border-radius: 8px;
  margin-bottom: 12px;
  box-shadow: 0 4px 12px rgba(0,82,255,0.25);
}}
.header-text h1 {{
  font-size: 18pt;
  font-family: Georgia, serif;
  letter-spacing: 1px;
  margin-bottom: 2px;
}}
.header-text .subtitle {{
  font-size: 8pt;
  opacity: 0.85;
  text-transform: uppercase;
  letter-spacing: 0.16em;
}}
.header-text .meta {{
  font-size: 8pt;
  margin-top: 4px;
  opacity: 0.8;
}}

/* Identificacao */
.identificacao {{
  background: #F8FAFC;
  border-left: 4px solid #0052FF;
  padding: 8px 14px;
  margin-bottom: 12px;
  border-radius: 4px;
}}
.identificacao .empresa {{ font-size: 11pt; font-weight: 700; color: #0F172A; }}
.identificacao .dados {{ font-size: 8.5pt; color: #475569; margin-top: 2px; }}

/* KPIs Grid */
.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 14px;
}}
.kpi {{
  background: linear-gradient(135deg, #ffffff 0%, #F8FAFC 100%);
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  padding: 10px 12px;
  text-align: center;
  position: relative;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}}
.kpi-label {{
  font-size: 7pt;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #64748B;
  font-weight: 600;
  margin-bottom: 3px;
}}
.kpi-value {{
  font-size: 14pt;
  font-weight: 800;
  color: #0F172A;
  font-family: 'Consolas', monospace;
}}
.kpi-value.danger {{ color: #DC2626; }}
.kpi-value.warning {{ color: #D97706; }}
.kpi-value.success {{ color: #16A34A; }}
.kpi-value.primary {{ color: #0052FF; }}
.kpi-sub {{
  font-size: 7pt;
  color: #94A3B8;
  margin-top: 2px;
}}

/* Achados */
.achados-title {{
  font-size: 11pt;
  font-weight: 700;
  color: #0F172A;
  margin: 10px 0 6px 0;
  padding-left: 8px;
  border-left: 3px solid #DC2626;
}}
.achados-grid {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
  margin-bottom: 12px;
}}
.achado {{
  border: 1px solid #E2E8F0;
  border-top: 3px solid;
  border-radius: 4px;
  padding: 8px 10px;
  background: white;
  min-height: 130px;
}}
.achado.critico {{ border-top-color: #DC2626; background: #FEF2F2; }}
.achado.alto {{ border-top-color: #D97706; background: #FFFBEB; }}
.achado.medio {{ border-top-color: #0052FF; background: #EFF6FF; }}
.achado-num {{
  font-size: 16pt;
  font-weight: 800;
  font-family: Georgia, serif;
}}
.achado.critico .achado-num {{ color: #DC2626; }}
.achado.alto .achado-num {{ color: #D97706; }}
.achado.medio .achado-num {{ color: #0052FF; }}
.achado-titulo {{
  font-size: 8.5pt;
  font-weight: 700;
  color: #0F172A;
  margin: 2px 0 4px 0;
  line-height: 1.2;
}}
.achado-valor {{
  font-size: 11pt;
  font-weight: 800;
  font-family: 'Consolas', monospace;
  color: #DC2626;
  margin: 4px 0;
}}
.achado-desc {{
  font-size: 7.5pt;
  color: #64748B;
  line-height: 1.35;
}}

/* Recomendacoes */
.rec-title {{
  font-size: 11pt;
  font-weight: 700;
  color: #0F172A;
  margin: 8px 0 6px 0;
  padding-left: 8px;
  border-left: 3px solid #0052FF;
}}
table.rec {{
  width: 100%;
  border-collapse: collapse;
  font-size: 8pt;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}
table.rec th {{
  background: linear-gradient(180deg, #0F172A, #1E3A8A);
  color: #fff;
  padding: 5px 8px;
  text-align: left;
  font-weight: 600;
  font-size: 8pt;
}}
table.rec td {{
  padding: 4px 8px;
  border-bottom: 1px solid #E2E8F0;
  font-size: 8pt;
}}
table.rec tr:nth-child(even) td {{ background: #F8FAFC; }}
.prazo {{
  font-weight: 700;
  text-align: center;
}}
.prazo.urgente {{ color: #DC2626; }}
.prazo.medio {{ color: #D97706; }}

/* Footer */
.footer {{
  margin-top: 8px;
  padding: 6px 10px;
  background: #F1F5F9;
  border-radius: 4px;
  font-size: 7pt;
  color: #64748B;
  text-align: center;
}}
.footer strong {{ color: #0F172A; }}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  {html_logo_inline()}
  <div class="header-text">
    <h1>ORGATEC</h1>
    <div class="subtitle">Apresentacao Executiva · Auditoria Bancaria</div>
    <div class="meta">Gerado em {agora} · Documento sintetico para tomada de decisao</div>
  </div>
</div>

<!-- Identificacao -->
<div class="identificacao">
  <div class="empresa">LOCAR TRANSPORTE DE BOVINOS LTDA</div>
  <div class="dados">
    CNPJ 05.509.396/0001-10 · Socio unico: Renato Costa Esperidiao Jr (CPF 931.891.171-87) ·
    Conta Sicoob 158083-3 (Ag 3333-2) · Periodo auditado: 01/01 a 14/05/2026
  </div>
</div>

<!-- KPIs -->
<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-label">Transacoes</div>
    <div class="kpi-value primary">7.110</div>
    <div class="kpi-sub">em 4,5 meses</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Volume Bruto</div>
    <div class="kpi-value">R$ 70,2M</div>
    <div class="kpi-sub">creditos+debitos</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Anualizado</div>
    <div class="kpi-value danger">R$ 187,3M</div>
    <div class="kpi-sub">39x teto EPP</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">CNPJs Identificados</div>
    <div class="kpi-value primary">616</div>
    <div class="kpi-sub">via base RFB</div>
  </div>
</div>

<!-- Achados -->
<div class="achados-title">Achados Criticos de Auditoria</div>
<div class="achados-grid">
  <div class="achado critico">
    <div class="achado-num">I</div>
    <div class="achado-titulo">Desenquadramento EPP</div>
    <div class="achado-valor">39x</div>
    <div class="achado-desc">Empresa EPP (limite R$ 4,8M/ano) movimentou R$ 187,3M projetado anual. Desenquadramento retroativo obrigatorio.</div>
  </div>
  <div class="achado critico">
    <div class="achado-num">II</div>
    <div class="achado-titulo">Subcapitalizacao</div>
    <div class="achado-valor">1:468</div>
    <div class="achado-desc">Capital R$ 400k vs giro R$ 187M/ano. Razao critica pode caracterizar simulacao societaria (art. 50 CC).</div>
  </div>
  <div class="achado alto">
    <div class="achado-num">III</div>
    <div class="achado-titulo">Partes Relacionadas</div>
    <div class="achado-valor">R$ 18,8M</div>
    <div class="achado-desc">LOCAR LOCADORA + MAQUINAS + Renato PF movimentam recursos sem lastro contratual documentado.</div>
  </div>
  <div class="achado alto">
    <div class="achado-num">IV</div>
    <div class="achado-titulo">MEIs Acima do Teto</div>
    <div class="achado-valor">32</div>
    <div class="achado-desc">Fornecedores MEI com volume anualizado > R$ 81k. Risco de pejotizacao e responsabilidade solidaria.</div>
  </div>
  <div class="achado critico">
    <div class="achado-num">V</div>
    <div class="achado-titulo">Retencoes Nao Recolhidas</div>
    <div class="achado-valor">R$ 488k</div>
    <div class="achado-desc">PIS+COFINS+CSLL+IRRF+INSS estimados para 5 meses. Multa 75-150% + SELIC se nao regularizado.</div>
  </div>
</div>

<!-- Acoes prioritarias -->
<div class="rec-title">Acoes Prioritarias com Prazo</div>
<table class="rec">
  <thead>
    <tr>
      <th style="width:5%">#</th>
      <th style="width:42%">Acao Recomendada</th>
      <th style="width:10%">Prazo</th>
      <th style="width:43%">Risco se nao executar</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>1</strong></td>
      <td>Apurar e recolher retencoes na fonte via denuncia espontanea (art. 138 CTN)</td>
      <td class="prazo urgente">30 dias</td>
      <td>Multa 75-150% + juros SELIC + representacao fiscal (Lei 8.137/90)</td>
    </tr>
    <tr>
      <td><strong>2</strong></td>
      <td>Investigar 17 pagamentos pos-baixa ao Percival Dias (R$ 35.626,89)</td>
      <td class="prazo urgente">30 dias</td>
      <td>Glosa de despesas + risco de lavagem (Lei 9.613/98)</td>
    </tr>
    <tr>
      <td><strong>3</strong></td>
      <td>Avaliar desenquadramento retroativo do regime EPP/Simples Nacional</td>
      <td class="prazo medio">60 dias</td>
      <td>Auto de infracao RFB com cobranca de tributos pelo regime correto</td>
    </tr>
    <tr>
      <td><strong>4</strong></td>
      <td>Notificar MEIs sobre desenquadramento e reclassificar contratos</td>
      <td class="prazo medio">60 dias</td>
      <td>Responsabilidade solidaria (Sumula 331 TST) + pejotizacao (art. 129 Lei 11.196)</td>
    </tr>
    <tr>
      <td><strong>5</strong></td>
      <td>Documentar lastro contratual das movimentacoes com partes relacionadas</td>
      <td class="prazo medio">90 dias</td>
      <td>Glosa de despesas + IRRF 27,5% sobre distribuicao disfarcada de lucros</td>
    </tr>
    <tr>
      <td><strong>6</strong></td>
      <td>Promover aumento de capital social compativel com o porte real</td>
      <td>120 dias</td>
      <td>Desconsideracao da personalidade juridica (art. 50 CC)</td>
    </tr>
    <tr>
      <td><strong>7</strong></td>
      <td>Implantar controle automatizado de retencoes (sistema + contador)</td>
      <td class="prazo urgente">30 dias</td>
      <td>Recorrencia das infracoes nos meses seguintes</td>
    </tr>
  </tbody>
</table>

<!-- Footer -->
<div class="footer">
  <strong>ORGATEC CONTABILIDADE E AUDITORIA LTDA</strong> ·
  Documento gerado pelo sistema OrgConc/OrgNeural2 v0.5.0 ·
  Confira o conteudo antes de apresentar ·
  <strong>Anexos:</strong> Carta de Constatacao + Relatorio Integrado + 5 conciliacoes mensais
</div>

</body>
</html>
"""


async def gerar_pdf(html_text):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html_text, wait_until="load")
            await page.pdf(
                path=str(OUT_PDF), format="A4",
                margin={"top": "8mm", "right": "10mm", "bottom": "8mm", "left": "10mm"},
                print_background=True,
                prefer_css_page_size=True,
            )
            await browser.close()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"PDF failed: {exc}")
        return False


async def main_async():
    print("Gerando Apresentacao Executiva (1 pagina)...")
    html = gerar_html()
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"  HTML: {OUT_HTML}")

    if await gerar_pdf(html):
        print(f"  PDF:  {OUT_PDF}")


if __name__ == "__main__":
    asyncio.run(main_async())
