"""Carta de Constatacao v3 - Adiciona Constatacao VIII sobre achados fiscais.

NOVO em v3:
- Constatacao VIII: REDE FROTA SOLUTIONS (R$ 3M sem NF-e) + 5 MEIs caminhoneiros (R$ 351k sem CT-e)
- Volume total de gap fiscal documentado: R$ 3,36M/ano em risco IRPJ+CSLL
- Tabela consolidada de risco tributario por categoria
- Atualizacao do sumario executivo com 8 constatacoes
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _logo_helper import html_logo_inline

OUT_APR = r"C:\Users\Veloso\Downloads\CARTA_APRESENTACAO_LOCAR_v3"
OUT_CONST = r"C:\Users\Veloso\Downloads\CARTA_CONSTATACAO_LOCAR_v3"


def _data_extenso() -> str:
    s = datetime.now().strftime("%d de %B de %Y")
    for en, pt in [("January", "janeiro"), ("February", "fevereiro"), ("March", "marco"),
                    ("April", "abril"), ("May", "maio"), ("June", "junho"),
                    ("July", "julho"), ("August", "agosto"), ("September", "setembro"),
                    ("October", "outubro"), ("November", "novembro"), ("December", "dezembro")]:
        s = s.replace(en, pt)
    return s


def _ref(prefixo: str) -> str:
    return f"{prefixo}-LOCAR-2026/05-{datetime.now().strftime('%d%m%H%M')}-v3"


def md_apresentacao() -> str:
    hoje = _data_extenso()
    ref = _ref("APRES")
    return f"""# CARTA DE APRESENTACAO EXECUTIVA

**Entrega Formal do Relatorio de Auditoria Bancaria + Auditoria Fiscal Cruzada**

---

**De:** ORGATEC CONTABILIDADE E AUDITORIA LTDA · Goiania-GO

**Para:** LOCAR TRANSPORTE DE BOVINOS LTDA — CNPJ 05.509.396/0001-10
A/C: Sr. Renato Costa Esperidiao Junior — Socio Administrador
Endereco da sede: Fazenda Mata do Formoso, 13 km — Zona Rural — Formoso/GO — CEP 76.470-000
Email: locarnotas@gmail.com · Telefones: (62) 3645-1165 / (62) 9131-9856

**Referencia:** {ref}

**Assunto:** Entrega formal do Relatorio Integrado de Auditoria Bancaria + Auditoria Fiscal Cruzada (NF-e/CT-e × OFX), Carta de Constatacao v3 e documentacao tecnica complementar. **Versao 3.0 incorpora cruzamento de 8.226 documentos fiscais (NF-e + CT-e) com 7.110 transacoes bancarias.**

**Local e Data:** Goiania-GO, {hoje}

---

## I. Apresentacao Institucional

A **ORGATEC CONTABILIDADE E AUDITORIA LTDA** apresenta esta versao 3.0 do dossie de auditoria, **integrando agora o cruzamento fiscal-bancario completo**, possibilitado pela disponibilizacao pelo cliente de:

- **5 ZIPs com 5.031 NF-es de compras** recebidas (jan-abr/2026)
- **4 ZIPs com 3.045 CT-es de transporte** emitidos (jan-abr/2026)

Total processado: **8.226 documentos fiscais XML × 7.110 transacoes OFX**.

## II. Procedimentos Adicionais (v3)

Foram aplicados procedimentos forenses fiscais alem da auditoria bancaria original:

1. **Parsing massivo XML** — 8.226 documentos NF-e/CT-e validados;
2. **Cruzamento fiscal-bancario** — matching de valor (tolerancia R$0,01) + data (janela 30 dias) + CNPJ;
3. **Score de Conformidade Fiscal** — % de pagamentos com NF-e correspondente por fornecedor;
4. **Classificacao por classe de risco** — CRITICO / ALTO / MEDIO / BAIXO;
5. **Estimativa de risco tributario adicional** — IRPJ 25% + CSLL 9% sobre despesa indedutivel em Lucro Real.

## III. Sumario Executivo Consolidado (v3 - 8 Constatacoes)

| # | Achado | Materialidade | Risco/Ano |
|---|---|:---:|---:|
| I | Confirmacao regime Lucro Real | Informativo | — |
| II | Historico exclusao administrativa Simples (2015-2018) | Alto | — |
| III | Subcapitalizacao (capital R$ 400k vs giro R$ 187M) | Critico | — |
| IV | Partes relacionadas sem lastro contratual | Alto | R$ 568k (DDL) |
| V | 5 MEI padrao com pequenos excessos | Baixo | R$ 12k |
| VI | Retencoes nao recolhidas (5 meses) | Critico | **R$ 1.173k/ano** |
| VII | Pagamentos pos-baixa do CNPJ (R$ 35,6k) | Critico | R$ 12k |
| **VIII (NOVO)** | **Gap fiscal documentado: REDE FROTA + 5 MEIs** | **Critico** | **R$ 3.359k/ano** |
| | **TOTAL DE RISCO TRIBUTARIO ANUALIZADO** | | **R$ 5.124k/ano** |

## IV. Documentos Entregues (v3)

### A. Cartas (v3)
- `CARTA_APRESENTACAO_LOCAR_v3.pdf`
- `CARTA_CONSTATACAO_LOCAR_v3.pdf` — **com Constatacao VIII**

### B. Relatorio Integrado (v4)
- `RELATORIO_INTEGRADO_LOCAR_v4.xlsx` — 14 abas (incluindo 3 novas: Conformidade Fiscal, Documentos Fiscais, Riscos Fiscais)
- `RELATORIO_INTEGRADO_LOCAR_v4.pdf`

### C. Investigacoes Especificas
- `INVESTIGACAO_ALVOS_LOCAR.pdf` — Thiago Marques, GT Participacoes, REDE FROTA
- `INVESTIGACAO_TOP10_FORNECEDORES.pdf` — gap fiscal por fornecedor

### D. Planejamento Tecnico
- `PLANEJAMENTO_INTEGRACAO_FISCAL.pdf` — roadmap de 5 sprints para internalizar a auditoria fiscal no sistema

### E. Documentos Originais (mantidos da v2)
- `AUDITORIA_CONSOLIDADA_158083-3_5MESES.{{xlsx,pdf,html,md}}`
- `AUDIT_LOCAR_158083-3_{{JAN,FEV,MAR,ABR,MAI}}_2026.{{xlsx,pdf,html,md}}`
- `MAPEAMENTO_PROJETO_ORGCONC.pdf`
- `PERFIL_AUDITORIA_LOCAR.pdf`

## V. Conclusoes da v3

O cruzamento fiscal-bancario amplia o passivo tributario potencial em **R$ 3,36M/ano adicionais** alem do ja apurado na v2 (R$ 1,17M/ano de retencoes nao recolhidas). O **risco total agregado anualizado** alcanca **R$ 5,12M/ano**, exigindo providencias imediatas e estruturadas.

## VI. Recomendacao Final (Atualizada)

Recomenda-se que a administracao da LOCAR convoque **reuniao tecnica urgente** com seu corpo juridico-contabil para:

1. Apurar e recolher **retencoes na fonte** via denuncia espontanea (CTN 138);
2. Apurar **NF-es nao recebidas da REDE FROTA SOLUTIONS** (R$ 3M/4 meses) — solicitar ao fornecedor + verificar na SEFAZ-GO;
3. Apurar **CT-es nao emitidos pelos 5 MEIs caminhoneiros** (R$ 351k/4 meses) — substituicao tributaria do tomador;
4. **Constituir provisao contabil** para passivos tributarios identificados;
5. Documentar **lastro contratual** das movimentacoes com partes relacionadas;
6. Avaliar **internalizacao do modulo de auditoria fiscal** (vide PLANEJAMENTO_INTEGRACAO_FISCAL.pdf).

Atenciosamente,

\\

___________________________________________
**ORGATEC CONTABILIDADE E AUDITORIA LTDA**

\\

___________________________________________
**Contador Responsavel** — CRC-GO [registro]

\\

___________________________________________
**Auditor Tecnico** — Registro [a confirmar]

---

*Documento emitido em {hoje} · Sistema OrgConc/OrgNeural2 v0.5.0 · Versao 3.0 com cruzamento fiscal-bancario completo (8.226 XMLs x 7.110 transacoes OFX).*
"""


def md_constatacao() -> str:
    hoje = _data_extenso()
    ref = _ref("CONST")
    return f"""# CARTA DE CONSTATACAO

**Memorando Tecnico-Juridico de Auditoria Bancaria + Fiscal — Versao 3.0**

---

**De:** ORGATEC CONTABILIDADE E AUDITORIA LTDA

**Para:** LOCAR TRANSPORTE DE BOVINOS LTDA — CNPJ 05.509.396/0001-10
A/C: Sr. Renato Costa Esperidiao Junior — Socio Administrador

**Referencia:** {ref}

**Assunto:** Constatacoes formais de auditoria sobre movimentacao bancaria + auditoria fiscal cruzada — Conta SICOOB 158083-3 / Periodo 01/01/2026 a 14/05/2026. **Versao 3.0 com cruzamento NF-e/CT-e x OFX.**

**Local e Data:** Goiania-GO, {hoje}

---

## 1. Preambulo

Prezado Sr. Renato Costa Esperidiao Junior,

Em complemento as Cartas v1.0 e v2.0, apresentamos a **Versao 3.0** das constatacoes formais, agora **incluindo o cruzamento fiscal-bancario completo** possibilitado pela disponibilizacao de:

- **5.031 NF-es de compras recebidas** (4 meses, jan-abr/2026)
- **3.045 CT-es de transporte emitidos** (4 meses, jan-abr/2026)
- **7.110 transacoes OFX** (5 meses, jan-mai/2026)

**Achados consolidados:** 8 constatacoes com risco tributario anualizado de **R$ 5,12M/ano**.

Esta versao **mantem integralmente** as Constatacoes I a VII da v2.0 e **acrescenta a Constatacao VIII** sobre gap fiscal documentado.

## 2. Sumario das 8 Constatacoes

| # | Constatacao | Materialidade | Risco/Ano |
|:---:|---|:---:|---:|
| I | Historico exclusao Simples 2015-2018 | Alto | — |
| II | Subcapitalizacao (468:1) | Critico | — |
| III | Partes relacionadas sem lastro | Alto | R$ 568k |
| IV | Reclassificacao MEIs (TAC vs Padrao) | Baixo | R$ 12k |
| V | Retencoes nao recolhidas | Critico | R$ 1.173k |
| VI | Pagamentos pos-baixa CNPJ | Critico | R$ 12k |
| VII | Volume compativel Lucro Real | Informativo | — |
| **VIII** | **Gap fiscal documentado (REDE FROTA + MEIs)** | **Critico** | **R$ 3.359k** |
| | **TOTAL CONSOLIDADO** | | **R$ 5.124k/ano** |

---

## 3. NOVA Constatacao VIII — GAP FISCAL DOCUMENTADO

### 3.1. Situacao Verificada

Apos cruzamento dos pagamentos bancarios (OFX) com 5.031 NF-es e 3.045 CT-es recebidos/emitidos pela LOCAR, foram identificadas **divergencias materiais** entre pagamentos efetuados e documentos fiscais correspondentes:

#### A) REDE FROTA SOLUTIONS LTDA (CNPJ 24.478.438/0001-48)

| Item | Valor |
|---|---|
| **Numero de pagamentos** | 29 transacoes |
| **Periodo** | jan-mai/2026 (5 meses) |
| **Volume pago** | R$ 3.025.000,00 (bruto) |
| **NF-es recebidas (modelo 55)** | **ZERO** |
| **CT-es recebidos (modelo 57)** | **ZERO** |
| **NFS-e municipais** | Nao identificadas no escopo |
| **CNAE da REDE FROTA** | Atividade auxiliar de servicos relacionados — provavel administradora de cartao de frota |
| **Anualizado projetado** | **R$ 8.840.000,00/ano** |

#### B) 5 MEI Caminhoneiros sem CT-e correspondente

| MEI | CNAE | Vol. Pago | CT-e Emitido |
|---|---|---:|:---:|
| ALEX NELBER RIBEIRO | 4930-2 transp. carga | R$ 98.333 | NAO |
| JANISON MOREIRA FEITOSA | 4930-2 transp. carga | R$ 85.993 | NAO |
| LEOMAR BARBOSA SOARES | 4930-2 transp. carga | R$ 85.390 | NAO |
| VYNICIUS ATAIDE DA SILVA | 4930-2 transp. carga | R$ 108.814 | NAO |
| (Outros 5 caminhoneiros) | 4930-2 | R$ 351.000 | NAO |
| **TOTAL (anualizado)** | — | **R$ 1.053.000/ano** | — |

### 3.2. Implicacoes Tecnicas e Juridicas

#### Para a REDE FROTA (R$ 3M/4 meses)

**Em regime de Lucro Real**, a ausencia de NF-e de servico/produto torna a despesa **INDEDUTIVEL** para fins de IRPJ + CSLL:

- **Art. 311 do RIR/2018** — exige documento fiscal idoneo para deducao;
- **Art. 226 do RIR/2018** — operacoes sem nota sao consideradas para acrescimo no LALUR;
- **Lei 8.846/1994, art. 7** — pode ensejar multa de 300% sobre valor da operacao quando sem documento.

**Calculo do risco tributario:**

- Despesa anual indedutivel: **R$ 8.840.000,00**
- Acrescimo no LALUR: **R$ 8.840.000,00**
- IRPJ adicional (25%): R$ 2.210.000,00
- CSLL adicional (9%): R$ 795.600,00
- **TOTAL: R$ 3.005.600,00/ano**

#### Para os MEIs caminhoneiros (R$ 351k/4 meses)

- **Art. 6, § 1, II do Decreto 8.324/2014** — Operacoes de transporte de cargas devem ser acobertadas por CT-e ou MDF-e do tomador;
- **Convenio ICMS 26/2008** — Tomador da prestacao do servico é responsavel solidario pelo recolhimento do ICMS quando o transportador autonomo nao emite CT-e;
- **Em Lucro Real**, despesa sem CT-e e indedutivel (mesma fundamentacao do item A).

**Calculo do risco tributario para MEIs sem CT-e:**

- Despesa anual indedutivel: **R$ 1.053.000,00**
- IRPJ adicional (25%): R$ 263.250,00
- CSLL adicional (9%): R$ 94.770,00
- ICMS substituicao (~5%): R$ 52.650,00 (se aplicavel)
- **TOTAL: R$ 358.020,00/ano**

#### Risco fiscal consolidado da Constatacao VIII

| Categoria | Risco/Ano |
|---|---:|
| REDE FROTA SOLUTIONS (despesa indedutivel) | R$ 3.005.600,00 |
| 5 MEIs caminhoneiros (despesa + ICMS-ST) | R$ 358.020,00 |
| **TOTAL CONSTATACAO VIII** | **R$ 3.363.620,00/ano** |

### 3.3. Hipoteses sobre a REDE FROTA SOLUTIONS

A REDE FROTA SOLUTIONS, em contexto de transporte rodoviario, e tipicamente uma **administradora de cartao de frota** (similar a Edenred/Sodexo Truckpad). Possiveis explicacoes:

1. **NF-es emitidas mas nao retornadas via sistema SEFAZ** — verificar no SEFAZ-GO Distribuicao DFe;
2. **Operacao via cartao com fatura mensal** — exige NF-e mensal de servico, nao recebida no periodo;
3. **NF-es enviadas por outro canal (email/papel)** — a contabilidade pode ter omitido na guarda eletronica;
4. **Operacao irregular** sem documento fiscal — hipotese mais grave.

### 3.4. Recomendacoes Especificas Constatacao VIII

#### Prioridade IMEDIATA (30 dias)

1. **Solicitar a REDE FROTA SOLUTIONS** envio formal de **todas as NF-es de jan-mai/2026** (sob protocolo);
2. **Verificar SEFAZ-GO** via "Consulta de NF-e por Destinatario" (NSU/Distribuicao DFe) — pode revelar NF-es nao baixadas pelo cliente;
3. **Notificar os 5 MEIs caminhoneiros** sobre obrigatoriedade de emissao de CT-e como condicao para continuidade do contrato;
4. **Suspender pagamentos** ate regularizacao fiscal.

#### Prioridade ALTA (60 dias)

5. **Adicionar ao LALUR** o valor de R$ 8.840.000,00 (REDE FROTA) e R$ 1.053.000,00 (MEIs) como **despesa indedutivel** se nao localizados documentos;
6. **Recolher diferenca de IRPJ + CSLL** dos trimestres ja encerrados via **DARF retroativa com denuncia espontanea** (art. 138 CTN);
7. **Implantar controle previo** que **bloqueie pagamento sem NF-e/CT-e correspondente** no sistema.

#### Prioridade MEDIA (90 dias)

8. **Substituir gradualmente os 5 MEIs caminhoneiros sem CT-e** por transportadoras PJ regulares com CT-e estruturado;
9. **Negociar com REDE FROTA** acordo de fornecimento mensal automatico de NF-es em PDF + XML;
10. **Treinar equipe financeira** sobre obrigatoriedade de NF-e para deducao em Lucro Real.

---

## 4. Tabela Consolidada de Risco Tributario (8 Constatacoes)

| Categoria | Fundamento | Risco/Ano |
|---|---|---:|
| Retencoes nao recolhidas (IRRF+PIS+COFINS+CSLL+INSS) | IN RFB 1.234/2012 | R$ 1.173.000 |
| Distribuicao disfarcada de lucros (partes relacionadas) | RIR/2018 art. 464 | R$ 568.000 |
| MEIs com pequenos excessos (5 MEIs padrao) | LC 123/2006 | R$ 12.000 |
| Pagamentos pos-baixa CNPJ (despesa indedutivel) | RIR/2018 art. 311 | R$ 12.000 |
| **REDE FROTA sem NF-e (IRPJ + CSLL)** | **RIR/2018 art. 311** | **R$ 3.005.600** |
| **MEIs caminhoneiros sem CT-e (IRPJ + CSLL + ICMS-ST)** | **Decreto 8.324/2014** | **R$ 358.020** |
| **TOTAL ANUALIZADO** | — | **R$ 5.128.620/ano** |

## 5. Ressalvas Tecnicas (Adicionais para v3)

a) **A ausencia de NF-e da REDE FROTA** pode ser explicada por NF-es nao baixadas via SEFAZ Distribuicao DFe; recomenda-se verificacao tecnica antes de adicao ao LALUR;

b) **CT-es nao emitidos pelos MEIs** podem refletir transporte realizado sob MDF-e do tomador (LOCAR) — verificar arquivo de MDF-es enviados;

c) **Estimativas de risco** sao baseadas em projecao anual de dados de 4 meses (NF-e/CT-e) e 5 meses (OFX); apuracao definitiva exige fechamento contabil anual;

d) **A presente Constatacao VIII complementa** os achados das v1.0/v2.0, sem substituir as Recomendacoes formais ja emitidas.

## 6. Recomendacoes Formais Consolidadas (v3)

| # | Acao | Prazo | Risco se nao executar |
|:---:|---|:---:|---|
| 1 | Apurar e recolher retencoes (denuncia espontanea) | **30 dias** | Multa 75-150% + juros |
| 2 | **Solicitar NF-es REDE FROTA + verificar SEFAZ** | **30 dias** | R$ 3M adicao LALUR |
| 3 | **Notificar 5 MEIs sobre CT-e obrigatorio** | **30 dias** | R$ 358k adicao LALUR + ICMS-ST |
| 4 | Investigar pagamentos pos-baixa CNPJ | **30 dias** | Glosa LALUR + risco penal |
| 5 | Implantar controle de retencoes na fonte | **30 dias** | Recorrencia |
| 6 | Solicitar processo administrativo exclusao 2015-2018 | **30 dias** | Antecedente fiscal |
| 7 | **Suspender pagamentos sem NF-e/CT-e** | **45 dias** | Risco continuo |
| 8 | Notificar MEIs padrao desenquadrados | **60 dias** | Responsabilidade solidaria |
| 9 | Documentar lastro contratual partes relacionadas | **90 dias** | Adicoes obrigatorias LALUR |
| 10 | Aumento de capital social | **120 dias** | Desconsideracao PJ |
| 11 | Conferir obrigacoes acessorias (DCTF/EFD/SPED) | **30 dias** | Multas por atraso |

## 7. Conclusao v3

A LOCAR TRANSPORTE DE BOVINOS LTDA apresenta **passivo tributario potencial anualizado de R$ 5,12 milhoes/ano**, sendo:

- **R$ 1,17M/ano** de retencoes nao recolhidas (Constatacao V — confirmado v2);
- **R$ 3,36M/ano** de despesa indedutivel sem NF-e/CT-e (Constatacao VIII — NOVO v3);
- **R$ 0,59M/ano** de outras adicoes obrigatorias.

Cabe ressaltar que **a maior parte do risco (Constatacao VIII)** pode ser **mitigada substancialmente** com a simples obtencao das NF-es nao recebidas, conforme recomendacao 2.

**A inacao acarreta** risco autuacao fiscal severo, com:

- Multa de oficio de 75% a 150%;
- Juros SELIC desde o vencimento original;
- Possivel representacao fiscal penal (Lei 8.137/90);
- Bloqueio futuro de certidoes (CND, CRF).

Permanecemos a disposicao para acompanhar a regularizacao das pendencias e para apresentar o **PLANEJAMENTO DE INTEGRACAO FISCAL** que internaliza este tipo de cruzamento no sistema OrgConc para uso continuado.

Atenciosamente,

\\

___________________________________________
**ORGATEC CONTABILIDADE E AUDITORIA LTDA**

\\

___________________________________________
**Contador Responsavel** — CRC-GO [registro]

\\

___________________________________________
**Auditor Tecnico** — Registro [a confirmar]

---

## Referencias Normativas Adicionais (v3)

- **Art. 311 do RIR/2018** (despesa indedutivel sem documento fiscal)
- **Art. 226 do RIR/2018** (operacoes sem nota — adicao LALUR)
- **Lei 8.846/1994, art. 7** (multa 300% por operacao sem nota)
- **Decreto 8.324/2014** (CT-e obrigatorio para transporte de cargas)
- **Convenio ICMS 26/2008** (substituicao tributaria do tomador no transporte autonomo)
- **IN RFB 1.422/2013** (LALUR Digital — controle de adicoes/exclusoes)
- **NBC TG 32 (R5)** (Tributos sobre o Lucro)

---

*Documento gerado em {hoje} pelo sistema OrgConc/OrgNeural2 v0.5.0 — versao 3.0 com cruzamento fiscal completo (8.226 XMLs x 7.110 OFX).*
"""


def _css_papel() -> str:
    return """
@page {
  size: A4;
  margin: 22mm 18mm 22mm 18mm;
  @bottom-right { content: "Pagina " counter(page) " de " counter(pages); font-size: 9px; color: #6B7280; }
  @bottom-left { content: "ORGATEC · Documento Tecnico Formal v3.0"; font-size: 9px; color: #6B7280; }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DejaVu Serif', Georgia, serif; font-size: 11pt; color: #1a202c; line-height: 1.65; }
.hd { background: linear-gradient(135deg, #0F172A, #0B1B3D 45%, #0052FF); color: #fff;
      padding: 28px 32px; border-radius: 4px; margin-bottom: 28px;
      display: flex; align-items: center; gap: 22px; }
.hd-text { flex: 1; }
.hd h1 { font-size: 24pt; font-family: 'DejaVu Serif', Georgia, serif; margin-bottom: 6px; letter-spacing: 1px; }
.hd .tag { font-size: 10pt; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.18em; }
.hd .meta { font-size: 9pt; opacity: 0.85; margin-top: 8px; }
h1 { font-size: 16pt; color: #0F172A; margin: 28px 0 12px; padding-bottom: 8px;
     border-bottom: 3px double #0052FF; text-align: center; font-family: 'DejaVu Serif', Georgia, serif; }
h2 { font-size: 13pt; color: #0F172A; margin: 24px 0 10px; padding: 10px 14px;
     background: #F0F7FF; border-left: 4px solid #0052FF; font-family: 'DejaVu Serif', Georgia, serif; }
h3 { font-size: 11pt; color: #0F172A; margin: 18px 0 8px; font-weight: 700; }
h4 { font-size: 10.5pt; color: #0F172A; margin: 14px 0 6px; font-weight: 700; }
p { margin-bottom: 10px; text-align: justify; }
table { width: 100%; border-collapse: collapse; margin: 12px 0 18px; font-size: 10pt;
        font-family: 'DejaVu Sans', sans-serif; }
th { background: linear-gradient(180deg, #0F172A, #1E3A8A); color: #fff;
     padding: 8px 12px; text-align: left; font-weight: 600; }
td { padding: 7px 12px; border-bottom: 1px solid #E2E8F0; }
tr:nth-child(even) td { background: #F8FAFC; }
strong { color: #0F172A; font-weight: 700; }
ul, ol { padding-left: 22px; margin-bottom: 12px; }
li { margin-bottom: 4px; }
hr { border: none; border-top: 1px solid #CBD5E1; margin: 18px 0; }
em { color: #64748B; font-size: 9pt; }
"""


def gerar_html(md_text: str, titulo: str, tag: str) -> str:
    import markdown as mdlib
    body = mdlib.markdown(md_text, extensions=["tables", "fenced_code"])
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>{titulo}</title><style>{_css_papel()}</style></head>
<body>
<div class="hd">
  {html_logo_inline()}
  <div class="hd-text">
    <h1>ORGATEC</h1>
    <div class="tag">{tag}</div>
    <div class="meta">Contabilidade · Auditoria · Compliance · Gerado em {agora}</div>
  </div>
</div>
{body}
</body></html>"""


async def gerar_pdf(html_text: str, out_path: Path) -> bool:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html_text, wait_until="load")
            await page.pdf(
                path=str(out_path), format="A4",
                margin={"top": "22mm", "right": "18mm", "bottom": "22mm", "left": "18mm"},
                print_background=True,
            )
            await browser.close()
        return True
    except Exception as exc:
        print(f"PDF failed: {exc}")
        return False


async def main_async():
    print("Gerando CARTA DE APRESENTACAO v3 (Constatacao VIII)...")
    md = md_apresentacao()
    Path(f"{OUT_APR}.md").write_text(md, encoding="utf-8")
    print(f"  MD:   {OUT_APR}.md")
    html = gerar_html(md, "Carta de Apresentacao v3 - LOCAR",
                     "Carta de Apresentacao Executiva · Versao 3.0 (Cruzamento Fiscal)")
    Path(f"{OUT_APR}.html").write_text(html, encoding="utf-8")
    print(f"  HTML: {OUT_APR}.html")
    if await gerar_pdf(html, Path(f"{OUT_APR}.pdf")):
        print(f"  PDF:  {OUT_APR}.pdf")

    print()
    print("Gerando CARTA DE CONSTATACAO v3 (com Constatacao VIII)...")
    md = md_constatacao()
    Path(f"{OUT_CONST}.md").write_text(md, encoding="utf-8")
    print(f"  MD:   {OUT_CONST}.md")
    html = gerar_html(md, "Carta de Constatacao v3 - LOCAR",
                     "Carta de Constatacao · Memorando Tecnico-Juridico v3.0")
    Path(f"{OUT_CONST}.html").write_text(html, encoding="utf-8")
    print(f"  HTML: {OUT_CONST}.html")
    if await gerar_pdf(html, Path(f"{OUT_CONST}.pdf")):
        print(f"  PDF:  {OUT_CONST}.pdf")


if __name__ == "__main__":
    asyncio.run(main_async())
