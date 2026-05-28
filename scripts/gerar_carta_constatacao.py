"""Gera Carta de Constatacao (Memorando Tecnico de Auditoria) - LOCAR TRANSPORTE.

Documento formal de auditoria com:
- Cabecalho ORGATEC (timbrado)
- Destinatario, data, referencia
- Objeto, escopo, procedimentos aplicados
- Constatacoes (5 achados)
- Ressalvas tecnicas
- Recomendacoes formais
- Conclusao e assinatura

Saidas: PDF, HTML, MD (XLSX e separado por nao ser tabular).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _logo_helper import html_logo_inline

OUT_BASE = r"C:\Users\Veloso\Downloads\CARTA_CONSTATACAO_LOCAR_TRANSPORTE"
OUT_MD = Path(f"{OUT_BASE}.md")
OUT_HTML = Path(f"{OUT_BASE}.html")
OUT_PDF = Path(f"{OUT_BASE}.pdf")


def gerar_md() -> str:
    hoje = datetime.now().strftime("%d de %B de %Y").replace(
        "January", "janeiro").replace("February", "fevereiro").replace("March", "marco").replace(
        "April", "abril").replace("May", "maio").replace("June", "junho").replace(
        "July", "julho").replace("August", "agosto").replace("September", "setembro").replace(
        "October", "outubro").replace("November", "novembro").replace("December", "dezembro")
    ref = f"AUDIT-LOCAR-2026/05-{datetime.now().strftime('%d%m%H%M')}"

    return f"""# CARTA DE CONSTATACAO

**Memorando Tecnico de Auditoria Bancaria**

---

**De:** ORGATEC CONTABILIDADE E AUDITORIA LTDA

**Para:** LOCAR TRANSPORTE DE BOVINOS LTDA — CNPJ 05.509.396/0001-10
A/C: Sr. Renato Costa Esperidiao Junior — Socio Administrador

**Referencia:** {ref}

**Assunto:** Constatacoes de auditoria sobre movimentacao bancaria — Conta Sicoob 158083-3 / Periodo 01/01/2026 a 14/05/2026

**Local e Data:** Goiania-GO, {hoje}

---

## 1. Preambulo

Prezado Sr. Renato Costa Esperidiao Junior,

Em atendimento aos procedimentos de auditoria contabil-fiscal aplicaveis a empresa **LOCAR TRANSPORTE DE BOVINOS LTDA**, inscrita no CNPJ sob o n. **05.509.396/0001-10**, e em conformidade com as Normas Brasileiras de Contabilidade (NBC TA 230, NBC TA 240 e NBC TA 320) e com a Instrucao Normativa RFB n. 2.119/2022, vimos por meio desta apresentar formalmente as **constatacoes** identificadas na analise dos extratos bancarios da conta corrente n. **158083-3**, agencia **3333-2**, mantida no **SICOOB - Banco Cooperativo do Brasil (Codigo 756)**, referente ao periodo de **01 de janeiro a 14 de maio de 2026**.

## 2. Objeto da Auditoria

A presente auditoria teve por objetivo:

a) Verificar a consistencia da movimentacao financeira da conta corrente principal da empresa auditada;
b) Identificar transacoes com partes relacionadas, fornecedores e prestadores de servico;
c) Avaliar a aderencia tributaria das movimentacoes (retencoes na fonte, IOF, tributos pagos);
d) Detectar anomalias forenses (pagamentos a CNPJs baixados, smurfing, padroes suspeitos);
e) Confrontar o porte declarado da empresa com o volume real movimentado.

## 3. Escopo e Procedimentos Aplicados

Foram analisadas **7.110 transacoes bancarias** distribuidas em 5 (cinco) extratos OFX mensais, perfazendo movimentacao bruta total de **R$ 70.253.530,38** no periodo.

Os procedimentos aplicados incluiram:

- **Procedimento 1**: Leitura e parsing dos arquivos OFX em formato SGML padrao;
- **Procedimento 2**: Classificacao automatica das transacoes em 6 estagios de matching (transferencia interna, CNPJ/CPF, NF-e, tarifa bancaria, tributo, contrato recorrente, alias/fuzzy);
- **Procedimento 3**: Enriquecimento de contrapartes via cruzamento com a base publica de CNPJs da Receita Federal (consulta via BrasilAPI - 551 CNPJs identificados);
- **Procedimento 4**: Aplicacao de detector forense (Risk Score 0-100) considerando situacao cadastral, porte, valor redondo, smurfing e carrossel;
- **Procedimento 5**: Classificacao tributaria automatica em 12 categorias (Retencao PJ, Retencao PF, IOF, Juros, Tarifa, Operacao de Credito, Pagamento de Tributo, etc.);
- **Procedimento 6**: Cruzamento com dados cadastrais extraidos do contrato social (2a Alteracao de 06/11/2024) e Cartao CNPJ emitido em 07/11/2024.

## 4. Constatacoes

### 4.1. CONSTATACAO I — DIVERGENCIA ENTRE PORTE DECLARADO E MOVIMENTACAO REAL

**Situacao verificada:** A empresa esta enquadrada na Receita Federal como **EPP - Empresa de Pequeno Porte** (Cartao CNPJ, campo "Porte"). O limite anual de receita bruta para EPP, conforme art. 3, II, da Lei Complementar 123/2006, e de **R$ 4.800.000,00**.

**Movimentacao apurada no periodo:**

| Indicador | Valor |
|---|---:|
| Movimentacao bruta (4,5 meses) | R$ 70.253.530,38 |
| Volume anualizado projetado | R$ 187.342.747,68 |
| Limite EPP (LC 123/2006) | R$ 4.800.000,00 |
| **Excesso projetado** | **R$ 182.542.747,68** |
| **Multiplo do teto EPP** | **39,03x** |

**Implicacao:** A empresa **deveria ter sido desenquadrada do Simples Nacional / regime EPP de forma retroativa**, conforme art. 30, II, da Lei Complementar 123/2006. Permanecer indevidamente enquadrada caracteriza recolhimento a menor de tributos federais (IRPJ, CSLL, PIS, COFINS), com risco de:

- Auto de infracao da Receita Federal com cobranca de tributos devidos no regime correto (Lucro Real ou Lucro Presumido) ;
- Multa de 75% sobre o tributo devido (art. 44, I, da Lei 9.430/96), podendo chegar a 150% em caso de fraude ou simulacao;
- Juros SELIC sobre os valores devidos retroativamente.

### 4.2. CONSTATACAO II — SUBCAPITALIZACAO

**Situacao verificada:** O capital social integralizado e de **R$ 400.000,00**, enquanto o giro anual projetado e de **R$ 187.342.747,68**.

**Razao volume/capital:** **468:1** (a empresa movimenta o equivalente a 468 vezes o seu capital social anualmente).

**Implicacao:** Caracteriza-se situacao de **subcapitalizacao** (capital insuficiente para suportar a operacao real), o que pode:

- Sinalizar incompatibilidade entre o capital social registrado e a atividade efetiva;
- Caracterizar **simulacao societaria** se o controlador (Renato Costa Esperidiao Jr) usar a estrutura para concentrar movimentacoes financeiras que excedem a capacidade declarada;
- Ensejar **desconsideracao da personalidade juridica** em caso de execucao fiscal ou trabalhista (CC art. 50, CTN art. 135).

**Recomendacao tecnica:** Promover **aumento de capital social** para valor compativel com o porte real da operacao, mediante alteracao contratual, ou efetuar **declaracao de subcapitalizacao** no LALUR e Bloco K do SPED.

### 4.3. CONSTATACAO III — PARTES RELACIONADAS NAO SEGREGADAS

**Situacao verificada:** Foram identificadas movimentacoes significativas com entidades vinculadas ao mesmo controlador (Renato Costa Esperidiao Jr):

| Parte Relacionada | Transacoes | Volume (R$) | Natureza |
|---|---:|---:|---|
| LOCAR LOCADORA E ??? (CNPJ a confirmar) | 73 | 6.733.631,85 | Recebimentos PIX MESMA TIT |
| LOCAR MAQUINAS E SERVICOS (CNPJ a confirmar) | 13 | 249.947,18 | Pagamentos / Recebimentos |
| RENATO COSTA ESPERIDIAO JR (PF socio) | 201 | 8.253.024,12 | Pro-labore / Dividendos / Mutuo |

**Implicacao:** A norma contabil obriga a divulgacao de **transacoes com partes relacionadas** (CPC 05 R1) e a destacacao destes valores no LALUR para fins de apuracao do IRPJ.

**Recomendacao tecnica:**

- Documentar cada movimentacao com **lastro contratual** (contratos de mutuo, atas de distribuicao de lucros, recibos de pro-labore);
- Manter **livro de partes relacionadas** atualizado nos termos do CPC 05 R1;
- Em caso de **distribuicao disfarcada de lucros** (art. 464 do RIR/2018), o valor sera tributado como dividendos com IRRF de 27,5% retroativo.

### 4.4. CONSTATACAO IV — MICROEMPREENDEDORES INDIVIDUAIS COM VOLUME ACIMA DO TETO

**Situacao verificada:** Foram identificados **32 (trinta e dois) fornecedores enquadrados como MEI** cujos pagamentos anualizados projetados excedem o teto legal de **R$ 81.000,00/ano** (Lei Complementar 123/2006, art. 18-A, § 1).

**Caso mais relevante:** 6 (seis) fornecedores recebem entre **R$ 67.000 e R$ 76.000 em 5 meses** (volume anualizado entre R$ 160.000 e R$ 184.000) — superior ao dobro do teto MEI.

**Implicacao:** A LOCAR, como **contratante**, pode ser solidariamente responsavel se for caracterizada **terceirizacao ilicita** (Sumula 331 do TST) ou **PJ disfarcada de PF** (art. 129 da Lei 11.196/2005 — pejotizacao).

**Recomendacoes tecnicas:**

- Notificar os MEIs sobre a obrigacao de **desenquadramento** (Resolucao CGSN 140/2018, art. 117);
- Reclassificar pagamentos como **prestacao de servico PJ** (sujeita a PIS+COFINS+CSLL 4,65% + IRRF 1,5%) ou como **autonomo PF** (IRRF tabela progressiva + INSS 11%);
- Avaliar **vinculo empregaticio** disfarcado se houver pessoalidade, subordinacao e habitualidade.

### 4.5. CONSTATACAO V — RETENCOES NA FONTE NAO RECOLHIDAS

**Situacao verificada:** A LOCAR, na condicao de **fonte pagadora** de servicos a pessoas juridicas e fisicas, **deveria ter retido tributos na fonte** sobre os pagamentos efetuados:

| Categoria | Tributos devidos | Aliquota | Volume estimado |
|---|---|:---:|---:|
| Pagamentos a PJ (servicos) | PIS+COFINS+CSLL+IRRF | 6,15% | R$ 456.552,83 |
| Pagamentos a PF (autonomos) | IRRF+INSS | ate ~27,5% | R$ 32.164,40 |
| **TOTAL ESTIMADO (5 meses)** | | | **R$ 488.717,23** |

**Fundamentos legais:**

- IN RFB 1.234/2012, art. 2 (retencoes PIS+COFINS+CSLL+IRRF sobre servicos PJ);
- Lei 10.833/2003, art. 30 (retencao para servicos profissionais);
- Lei 8.212/1991, art. 31 (INSS retido em servicos prestados por PF).

**Codigos de DARF aplicaveis:**

- Codigo **1708** (PIS+COFINS+CSLL+IRRF servicos PJ);
- Codigo **0588** (IRRF servico PF autonomo);
- Codigo **2631** (CSLL retida).

**Implicacao:** O nao recolhimento configura **infracao tributaria** (Lei 8.137/90), sujeitando a empresa a:

- Multa de oficio de **75% a 150%** sobre o tributo devido;
- Juros SELIC sobre o periodo;
- Possivel **representacao fiscal para fins penais** se houver dolo de sonegacao (art. 1 da Lei 8.137/90).

**Recomendacao urgente:** Apurar e recolher as retencoes via **DARFs retroativos com codigo 0204** (denuncia espontanea, art. 138 do CTN), o que afasta a multa de oficio mas mantem juros SELIC.

### 4.6. CONSTATACAO VI — PAGAMENTOS APOS BAIXA DO CNPJ

**Situacao verificada:** Foram identificadas **17 (dezessete) transacoes** efetuadas a **CNPJs ja BAIXADOS** na Receita Federal no momento do pagamento.

**Caso mais critico:**

- **Fornecedor:** PERCIVAL DIAS DA SILVA — CNPJ 63.567.345/0001-41
- **Situacao:** BAIXADO em 11/03/2026
- **Pagamentos posteriores:** 17 transacoes
- **Volume:** R$ 35.626,89
- **Defasagem maxima:** 63 dias apos a baixa

**Implicacoes graves:**

1. Pagamentos a CNPJ baixado podem caracterizar **simulacao** (art. 167, § 1, II, do CC) ou **fraude contra credores** (art. 159 do CC);
2. Os valores podem ser **glosados** como despesa dedutivel pelo Fisco (art. 311 do RIR/2018);
3. Em caso de notas fiscais emitidas apos a baixa, ha **emissao indevida de documento fiscal** (Lei 8.137/90).

**Recomendacoes:**

a) Investigar a natureza dos pagamentos (servico efetivo? mutuo? pagamento ao CPF do ex-MEI?);
b) Caso confirmada prestacao de servico, reclassificar como **autonomo PF** com retencao na fonte (IRRF tabela + INSS);
c) Caso nao confirmada, **estornar os lancamentos contabeis** e considerar a possibilidade de **lavagem de dinheiro** (Lei 9.613/98 - comunicacao ao COAF se aplicavel).

## 5. Ressalvas Tecnicas

a) **Identificacao de partes relacionadas LOCAR LOCADORA e LOCAR MAQUINAS:** A confirmacao dos CNPJs destas entidades depende de consulta complementar ao banco (truncamento de nome no extrato OFX impede identificacao automatica).

b) **Apuracao precisa de retencoes:** Os valores estimados de retencao (R$ 488.717,23) tem por base aliquotas padrao. A apuracao exata depende da **natureza efetiva dos servicos prestados** (assistencia tecnica, manutencao, locacao, etc.), o que so pode ser confirmado via cotejamento com **notas fiscais de servico** correspondentes — nao disponibilizadas para esta auditoria.

c) **Volume anualizado projetado:** O calculo de R$ 187.342.747,68 e projecao linear baseada em 4,5 meses. Pode haver sazonalidade nao capturada nesta janela.

d) **Movimentacao com sócio Renato Costa (R$ 8,25M):** Sem acesso a contratos de mutuo, atas de distribuicao de lucros ou folha de pagamento do administrador, nao foi possivel classificar definitivamente cada transacao individual.

## 6. Recomendacoes Formais e Prazos Sugeridos

| # | Acao | Prazo | Risco se nao executar |
|---|---|---|---|
| 1 | Apurar e recolher retencoes na fonte via denuncia espontanea | **30 dias** | Multa 75-150% + juros |
| 2 | Avaliar desenquadramento retroativo do regime EPP / Simples | **60 dias** | Auto de infracao RFB |
| 3 | Documentar lastro contratual das partes relacionadas | **90 dias** | Glosa de despesas + IRRF dividendos |
| 4 | Notificar MEIs sobre desenquadramento + revisar contratos | **60 dias** | Responsabilidade solidaria |
| 5 | Investigar pagamentos pos-baixa e estornar se aplicavel | **30 dias** | Glosa fiscal + risco penal |
| 6 | Promover aumento de capital social | **120 dias** | Desconsideracao PJ |
| 7 | Implantar controle de retencoes na fonte (sistema/contador) | **30 dias** | Recorrencia das infracoes |

## 7. Conclusao

Diante das constatacoes apresentadas, recomenda-se **PROVIDENCIAS IMEDIATAS** por parte da administracao da LOCAR TRANSPORTE DE BOVINOS LTDA para regularizar as questoes tributarias e contabeis identificadas, sob risco de **autuacao fiscal substancial** estimada em milhoes de reais (considerando tributos devidos pelo regime correto + multas de oficio + juros).

Esta Carta de Constatacao tem **natureza tecnica e nao acusatoria**, sendo destinada exclusivamente a orientar a administracao da empresa quanto a aderencia normativa.

Permanecemos a disposicao para esclarecimentos e para acompanhar a regularizacao das pendencias identificadas.

Atenciosamente,

\\

**ORGATEC CONTABILIDADE E AUDITORIA LTDA**

CNPJ [a confirmar] · CRC-GO [a confirmar]

\\

\\

___________________________________________
[Contador Responsavel — Nome e CRC]

___________________________________________
[Auditor Tecnico — Nome e Registro]

---

**ANEXOS ENTREGUES JUNTO A ESTA CARTA:**

1. AUDITORIA_LOCAR_TRANSPORTE_BOVINOS.pdf — Relatorio forense em 5 abas (XLSX) e versao impressa
2. AUDITORIA_CONSOLIDADA_158083-3_5MESES.pdf — Consolidado mensal com evolucao
3. AUDIT_LOCAR_158083-3_{{JAN,FEV,MAR,ABR,MAI}}_2026.{{pdf,xlsx}} — Conciliacao detalhada mes a mes (5 conjuntos)
4. PERFIL_AUDITORIA_LOCAR.pdf — Perfil cadastral da empresa cruzado com extratos
5. RELATORIO_ENRIQUECIDO_v3.xlsx — Cruzamento com base CNPJ RFB (551 contrapartes)

*Documento gerado eletronicamente pelo sistema OrgConc/OrgNeural2 - versao 0.5.0. Confira o conteudo antes de assinar.*

---

**REFERENCIAS NORMATIVAS CITADAS:**

- Lei Complementar 123/2006 (Simples Nacional / EPP)
- Lei 8.137/1990 (Crimes contra a ordem tributaria)
- Lei 9.430/1996 (Multas e juros)
- Lei 9.613/1998 (Lavagem de dinheiro / COAF)
- Lei 10.833/2003 (Retencao PIS+COFINS+CSLL)
- Lei 11.196/2005, art. 129 (Pejotizacao)
- Lei 8.212/1991 (INSS)
- IN RFB 1.234/2012 (Retencoes na fonte)
- IN RFB 2.119/2022 (Cartao CNPJ)
- Resolucao CGSN 140/2018 (MEI)
- CPC 05 R1 (Partes Relacionadas)
- NBC TA 230, 240, 320 (Normas de Auditoria)
- CC arts. 50, 159, 167 (Desconsideracao PJ, Fraude, Simulacao)
- CTN art. 135, 138 (Responsabilidade tributaria, Denuncia espontanea)
- RIR/2018 art. 311, 464 (Despesas e dividendos)
- Sumula 331 TST (Terceirizacao)
"""


def gerar_html(md_text: str) -> str:
    import markdown as mdlib
    body = mdlib.markdown(md_text, extensions=["tables", "fenced_code"])
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    css = """
@page { size: A4; margin: 22mm 18mm 22mm 18mm;
  @bottom-right { content: "Pagina " counter(page) " de " counter(pages); font-size: 9px; color: #6B7280; }
  @bottom-left { content: "Carta de Constatacao - LOCAR TRANSPORTE DE BOVINOS LTDA"; font-size: 9px; color: #6B7280; }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DejaVu Serif', Georgia, serif; font-size: 11pt; color: #1a202c; line-height: 1.65; }
.hd { background: linear-gradient(135deg, #0F172A, #0B1B3D 45%, #0052FF); color: #fff;
      padding: 28px 32px; border-radius: 4px; margin-bottom: 28px; display: flex; align-items: center; gap: 22px;}
.hd-text { flex: 1; }
.hd h1 { font-size: 24pt; font-family: 'DejaVu Serif', Georgia, serif; margin-bottom: 6px; letter-spacing: 1px; }
.hd .tag { font-size: 10pt; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.18em; }
.hd .meta { font-size: 9pt; opacity: 0.85; margin-top: 8px; }
h1 { font-size: 16pt; color: #0F172A; margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 3px double #0052FF; text-align: center; font-family: 'DejaVu Serif', Georgia, serif; }
h2 { font-size: 13pt; color: #0F172A; margin: 24px 0 10px; padding: 10px 14px; background: #F0F7FF; border-left: 4px solid #0052FF; font-family: 'DejaVu Serif', Georgia, serif; }
h3 { font-size: 11pt; color: #0F172A; margin: 18px 0 8px; font-weight: 700; }
p { margin-bottom: 10px; text-align: justify; }
table { width: 100%; border-collapse: collapse; margin: 12px 0 18px; font-size: 10pt;
        font-family: 'DejaVu Sans', sans-serif; }
th { background: linear-gradient(180deg, #0F172A, #1E3A8A); color: #fff; padding: 8px 12px; text-align: left; font-weight: 600; }
td { padding: 7px 12px; border-bottom: 1px solid #E2E8F0; }
tr:nth-child(even) td { background: #F8FAFC; }
strong { color: #0F172A; font-weight: 700; }
ul, ol { padding-left: 22px; margin-bottom: 12px; }
li { margin-bottom: 4px; }
hr { border: none; border-top: 1px solid #CBD5E1; margin: 18px 0; }
.assinatura { margin: 40px 0 20px; text-align: center; }
em { color: #64748B; font-size: 9pt; }
"""
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>Carta de Constatacao - LOCAR TRANSPORTE DE BOVINOS LTDA</title><style>{css}</style></head>
<body>
<div class="hd">
  {html_logo_inline()}
  <div class="hd-text">
    <h1>ORGATEC</h1>
    <div class="tag">Contabilidade · Auditoria · Compliance</div>
    <div class="meta">Documento Tecnico Formal · Gerado em {agora}</div>
  </div>
</div>
{body}
</body></html>"""


async def gerar_pdf(html_text: str) -> bool:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html_text, wait_until="load")
            await page.pdf(
                path=str(OUT_PDF), format="A4",
                margin={"top": "22mm", "right": "18mm", "bottom": "22mm", "left": "18mm"},
                print_background=True,
            )
            await browser.close()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"PDF failed: {exc}")
        return False


async def main_async():
    print("Gerando Carta de Constatacao...")
    md = gerar_md()
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"  MD:   {OUT_MD}")

    html = gerar_html(md)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"  HTML: {OUT_HTML}")

    if await gerar_pdf(html):
        print(f"  PDF:  {OUT_PDF}")


if __name__ == "__main__":
    asyncio.run(main_async())
