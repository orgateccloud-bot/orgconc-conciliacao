"""Gera duas cartas formais para LOCAR TRANSPORTE DE BOVINOS LTDA:

1. CARTA DE APRESENTACAO EXECUTIVA: documento de entrega do trabalho de
   auditoria, listando anexos, sumario executivo e procedimentos.

2. CARTA DE CONSTATACAO: memorando tecnico-juridico com as 6 constatacoes,
   ressalvas, recomendacoes com prazos e referencias normativas.

Saidas: PDF + HTML + MD para cada uma, com logo ORGATEC e estilo papel
timbrado profissional.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _logo_helper import html_logo_inline


# ─────────────────────────────────────────────────────────────────────────
# Saidas
# ─────────────────────────────────────────────────────────────────────────

OUT_APR_BASE = r"C:\Users\Veloso\Downloads\CARTA_APRESENTACAO_LOCAR"
OUT_CONST_BASE = r"C:\Users\Veloso\Downloads\CARTA_CONSTATACAO_LOCAR"


def _mes_pt(en: str) -> str:
    m = {"January": "janeiro", "February": "fevereiro", "March": "marco",
         "April": "abril", "May": "maio", "June": "junho", "July": "julho",
         "August": "agosto", "September": "setembro", "October": "outubro",
         "November": "novembro", "December": "dezembro"}
    return m.get(en, en.lower())


def _data_extenso() -> str:
    s = datetime.now().strftime("%d de %B de %Y")
    for en, pt in [("January", "janeiro"), ("February", "fevereiro"), ("March", "marco"),
                    ("April", "abril"), ("May", "maio"), ("June", "junho"),
                    ("July", "julho"), ("August", "agosto"), ("September", "setembro"),
                    ("October", "outubro"), ("November", "novembro"), ("December", "dezembro")]:
        s = s.replace(en, pt)
    return s


def _ref(prefixo: str) -> str:
    return f"{prefixo}-LOCAR-2026/05-{datetime.now().strftime('%d%m%H%M')}"


# ═══════════════════════════════════════════════════════════════════════
# CARTA DE APRESENTACAO EXECUTIVA
# ═══════════════════════════════════════════════════════════════════════


def md_apresentacao() -> str:
    hoje = _data_extenso()
    ref = _ref("APRES")
    return f"""# CARTA DE APRESENTACAO EXECUTIVA

**Entrega Formal do Relatorio de Auditoria Bancaria**

---

**De:** ORGATEC CONTABILIDADE E AUDITORIA LTDA · Goiania-GO

**Para:** LOCAR TRANSPORTE DE BOVINOS LTDA — CNPJ 05.509.396/0001-10
A/C: Sr. Renato Costa Esperidiao Junior — Socio Administrador
Endereco da sede: Fazenda Mata do Formoso, 13 km — Zona Rural — Formoso/GO — CEP 76.470-000
Email: locarnotas@gmail.com · Telefones: (62) 3645-1165 / (62) 9131-9856

**Referencia:** {ref}

**Assunto:** Entrega formal do Relatorio Integrado de Auditoria Bancaria, Carta de Constatacao e documentacao tecnica complementar.

**Local e Data:** Goiania-GO, {hoje}

---

## I. Apresentacao Institucional

A **ORGATEC CONTABILIDADE E AUDITORIA LTDA** apresenta-se como escritorio especializado em contabilidade fiscal, auditoria forense e compliance tributario para empresas de medio e grande porte, atuante no estado de Goias e regiao Centro-Oeste.

Para o presente engajamento, foram aplicados os procedimentos preconizados pelas:

- **NBC TA 230** — Documentacao de Auditoria
- **NBC TA 240** — Responsabilidade do Auditor em Relacao a Fraude
- **NBC TA 320** — Materialidade no Planejamento e Execucao da Auditoria
- **IN RFB 2.119/2022** — Cadastro Nacional da Pessoa Juridica
- **CPC 05 R1** — Divulgacao sobre Partes Relacionadas

## II. Objeto do Trabalho

Foi conduzida **auditoria bancaria forense** sobre os extratos da conta corrente n. **158083-3**, agencia 3333-2, mantida no **SICOOB - Banco Cooperativo do Brasil (Codigo 756)**, referente ao periodo de:

- **Inicio:** 01 de janeiro de 2026
- **Fim:** 14 de maio de 2026
- **Duracao:** 4,5 meses (5 extratos mensais analisados)
- **Total de transacoes:** 7.110 lancamentos
- **Movimentacao bruta:** R$ 70.253.530,38

Os documentos cadastrais examinados:

- 2a Alteracao e Consolidacao Contratual (06/11/2024)
- Cartao CNPJ emitido em 07/11/2024 (Receita Federal)
- 5 extratos OFX da conta 158083-3 (jan-mai/2026)

## III. Procedimentos Aplicados

Foram executados **6 procedimentos** sequenciais, com automacao via sistema OrgConc/OrgNeural2 (versao 0.5.0):

1. **Parsing e validacao** dos arquivos OFX em formato SGML, incluindo conferencia de saldo (LEDGERBAL) contra fluxo apurado;
2. **Classificacao em cascata** das transacoes em 6 estagios (transferencia interna, CNPJ/CPF, NF-e, tarifa bancaria, tributo, contrato);
3. **Enriquecimento de contrapartes** via cruzamento com a base publica de CNPJs da Receita Federal (BrasilAPI, 616 CNPJs identificados);
4. **Aplicacao de detectores forenses** — Risk Score 0-100 considerando situacao cadastral, porte, valor redondo, smurfing e carrossel;
5. **Classificacao tributaria** em 12 categorias (Retencao PJ/PF, IOF, Juros, Tarifa, Operacao de Credito, Pagamento de Tributo, etc.);
6. **Cruzamento com dados cadastrais** extraidos do contrato social + cartao CNPJ + relatorios complementares.

## IV. Sumario Executivo dos Achados

A auditoria identificou **achados criticos** que demandam regularizacao imediata por parte da administracao:

| # | Achado | Materialidade |
|---|---|:---:|
| I | Divergencia entre porte EPP declarado e movimentacao real (39x teto) | **Critico** |
| II | Subcapitalizacao (capital R$ 400k vs giro R$ 187M/ano) | **Critico** |
| III | Movimentacao com partes relacionadas sem lastro contratual claro | **Alto** |
| IV | 32 fornecedores enquadrados como MEI com volume superior ao teto | **Alto** |
| V | Retencoes na fonte nao recolhidas: **R$ 488.717,23 estimados em 5 meses** | **Critico** |
| VI | 17 pagamentos a CNPJ baixado (Percival Dias - R$ 35.626,89) | **Critico** |

O **detalhamento juridico-tecnico** de cada achado, com fundamentacao normativa, valores apurados e recomendacoes formais com prazos esta consolidado na **Carta de Constatacao** anexa.

## V. Documentos Entregues (Anexos)

Esta entrega contempla os seguintes anexos tecnicos:

### A. Apresentacao Executiva (1 pagina)
- `APRESENTACAO_EXECUTIVA_LOCAR.pdf` — sintese visual para reuniao de apresentacao

### B. Documento Tecnico-Juridico
- `CARTA_CONSTATACAO_LOCAR.pdf` — memorando formal com 6 constatacoes, ressalvas e recomendacoes

### C. Relatorio Integrado Completo
- `RELATORIO_INTEGRADO_LOCAR_v2.xlsx` — 11 abas com indice navegavel (Capa, Identificacao, Resumo, Transacoes, Disposicoes, Risk, CNPJs, Partes Relacionadas, MEIs, Status Tributario, Pos-Baixa)
- `RELATORIO_INTEGRADO_LOCAR_v2.pdf` — versao impressa
- `RELATORIO_INTEGRADO_LOCAR_v2.html` — versao web

### D. Relatorios Mensais (detalhe por mes)
- `AUDIT_LOCAR_158083-3_JAN2026.{{xlsx,pdf,html,md}}`
- `AUDIT_LOCAR_158083-3_FEV2026.{{xlsx,pdf,html,md}}`
- `AUDIT_LOCAR_158083-3_MAR2026.{{xlsx,pdf,html,md}}`
- `AUDIT_LOCAR_158083-3_ABR2026.{{xlsx,pdf,html,md}}`
- `AUDIT_LOCAR_158083-3_MAI2026.{{xlsx,pdf,html,md}}`

Cada relatorio mensal contem 7 abas: Resumo, Transacoes, Disposicoes Forenses (27 colunas), Risk Heatmap, CNPJs, Partes Relacionadas e Status Tributario.

### E. Perfil Cadastral
- `PERFIL_AUDITORIA_LOCAR.pdf` — perfil cadastral cruzado com movimentacao

### F. Auditoria Consolidada
- `AUDITORIA_CONSOLIDADA_158083-3_5MESES.{{xlsx,pdf,html,md}}` — visao agregada

## VI. Procedimentos para Esclarecimentos

Permanecemos a disposicao para:

- **Reuniao de apresentacao** dos achados (presencial ou videoconferencia);
- **Esclarecimentos tecnicos** sobre fundamentacao normativa;
- **Apoio na regularizacao** das pendencias identificadas (apuracao de retencoes, desenquadramento tributario, documentacao de partes relacionadas);
- **Implantacao de controles** preventivos para evitar recorrencia.

### Canal de contato:

- Email: orgatec1@hotmail.com
- Telefones: (62) 9 9294-9161 / (62) 3377-6815

Solicita-se confirmacao do recebimento desta entrega e dos anexos, preferencialmente em ate **5 dias uteis**.

## VII. Recomendacao Final

Diante da materialidade dos achados, recomenda-se que a administracao da LOCAR TRANSPORTE DE BOVINOS LTDA convoque **reuniao tecnica urgente** com seu corpo juridico-contabil para deliberar sobre:

1. As acoes prioritarias detalhadas na Carta de Constatacao (especialmente as de prazo de 30 dias);
2. A constituicao de **provisao contabil** adequada para os passivos tributarios identificados;
3. A regularizacao das retencoes na fonte via **denuncia espontanea** (art. 138 do CTN), afastando a multa de oficio.

Atenciosamente,

\\

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

*Documento emitido em {hoje} · Sistema OrgConc/OrgNeural2 v0.5.0 · Esta carta acompanha {{n_anexos}} arquivos digitais entregues em meio eletronico.*
"""


# ═══════════════════════════════════════════════════════════════════════
# CARTA DE CONSTATACAO
# ═══════════════════════════════════════════════════════════════════════


def md_constatacao() -> str:
    hoje = _data_extenso()
    ref = _ref("CONST")
    return f"""# CARTA DE CONSTATACAO

**Memorando Tecnico-Juridico de Auditoria Bancaria**

---

**De:** ORGATEC CONTABILIDADE E AUDITORIA LTDA

**Para:** LOCAR TRANSPORTE DE BOVINOS LTDA — CNPJ 05.509.396/0001-10
A/C: Sr. Renato Costa Esperidiao Junior — Socio Administrador

**Referencia:** {ref}

**Assunto:** Constatacoes formais de auditoria sobre movimentacao bancaria — Conta SICOOB 158083-3 / Periodo 01/01/2026 a 14/05/2026.

**Local e Data:** Goiania-GO, {hoje}

---

## 1. Preambulo

Prezado Sr. Renato Costa Esperidiao Junior,

Em atendimento aos procedimentos de auditoria contabil-fiscal aplicaveis a **LOCAR TRANSPORTE DE BOVINOS LTDA**, inscrita no CNPJ sob o n. **05.509.396/0001-10**, e em conformidade com as Normas Brasileiras de Contabilidade (NBC TA 230, NBC TA 240 e NBC TA 320) e com a Instrucao Normativa RFB n. 2.119/2022, vimos por meio desta apresentar formalmente as **constatacoes** identificadas na analise dos extratos bancarios da conta corrente n. **158083-3**, agencia **3333-2**, mantida no **SICOOB - Banco Cooperativo do Brasil (codigo 756)**, referente ao periodo de **01 de janeiro a 14 de maio de 2026**.

A movimentacao bruta apurada no periodo totaliza **R$ 70.253.530,38**, distribuida em **7.110 transacoes** lidas em 5 (cinco) extratos OFX mensais. As contrapartes foram enriquecidas mediante cruzamento com a base publica da Receita Federal, perfazendo **616 CNPJs identificados**.

## 2. Objeto da Auditoria

A presente auditoria teve por objetivo:

a) Verificar a consistencia da movimentacao financeira da conta corrente principal da empresa auditada;
b) Identificar transacoes com partes relacionadas, fornecedores e prestadores de servico;
c) Avaliar a aderencia tributaria das movimentacoes (retencoes na fonte, IOF, tributos pagos);
d) Detectar anomalias forenses (pagamentos a CNPJs baixados, smurfing, padroes suspeitos);
e) Confrontar o porte declarado da empresa com o volume real movimentado.

## 3. Constatacoes

### 3.1. CONSTATACAO I — DIVERGENCIA ENTRE PORTE DECLARADO E MOVIMENTACAO REAL

**Situacao verificada:** A empresa esta enquadrada na Receita Federal como **EPP - Empresa de Pequeno Porte** (Cartao CNPJ). O limite anual de receita bruta para EPP, conforme art. 3, II, da Lei Complementar 123/2006, e de **R$ 4.800.000,00**.

| Indicador | Valor |
|---|---:|
| Movimentacao bruta (4,5 meses) | R$ 70.253.530,38 |
| Volume anualizado projetado | **R$ 187.342.747,68** |
| Limite EPP (LC 123/2006) | R$ 4.800.000,00 |
| **Excesso projetado** | **R$ 182.542.747,68** |
| **Multiplo do teto EPP** | **39,03x** |

**Implicacao juridica:** A empresa **deveria ter sido desenquadrada do Simples Nacional / regime EPP de forma retroativa** (art. 30, II, LC 123/2006). Permanecer indevidamente enquadrada caracteriza recolhimento a menor de tributos federais, com risco de:

- Auto de infracao da RFB cobrando tributos pelo regime correto (Lucro Real / Presumido);
- Multa de 75% (art. 44, I, Lei 9.430/96), podendo chegar a 150% em caso de fraude;
- Juros SELIC sobre os valores retroativos.

### 3.2. CONSTATACAO II — SUBCAPITALIZACAO SIGNIFICATIVA

**Situacao verificada:** O capital social integralizado e de **R$ 400.000,00**, enquanto o giro anual projetado e de **R$ 187.342.747,68**.

**Razao volume/capital:** **468:1** (a empresa movimenta o equivalente a 468 vezes o seu capital social anualmente).

**Implicacao juridica:** Caracteriza-se situacao de **subcapitalizacao**, o que pode:

- Sinalizar incompatibilidade entre o capital social registrado e a atividade efetiva;
- Caracterizar **simulacao societaria** (art. 167, § 1, II, do Codigo Civil);
- Ensejar **desconsideracao da personalidade juridica** em execucao fiscal/trabalhista (CC art. 50, CTN art. 135).

**Recomendacao tecnica:** Promover **aumento de capital social** para valor compativel com o porte real, mediante alteracao contratual, OU efetuar **declaracao de subcapitalizacao** no LALUR e Bloco K do SPED.

### 3.3. CONSTATACAO III — PARTES RELACIONADAS NAO SEGREGADAS

**Situacao verificada:** Movimentacoes significativas com entidades vinculadas ao mesmo controlador (Renato Costa Esperidiao Jr):

| Parte Relacionada | Transacoes | Volume (R$) | Natureza |
|---|---:|---:|---|
| LOCAR LOCADORA E ??? (CNPJ a confirmar) | 73 | 6.733.631,85 | Recebimentos PIX MESMA TIT |
| LOCAR MAQUINAS E SERVICOS | 13 | 249.947,18 | Pagamentos / Recebimentos |
| RENATO COSTA ESPERIDIAO JR (PF) | 201 | 8.253.024,12 | Pro-labore / Dividendos / Mutuo |

**Implicacao normativa:** A norma contabil **CPC 05 R1** obriga a divulgacao de transacoes com partes relacionadas. O **art. 464 do RIR/2018** disciplina a distribuicao disfarcada de lucros, sujeita a IRRF de 27,5% retroativo.

**Recomendacao tecnica:**

- Documentar cada movimentacao com **lastro contratual** (contratos de mutuo, atas de distribuicao, recibos de pro-labore);
- Manter **livro de partes relacionadas** nos termos do CPC 05 R1;
- Verificar se ha distribuicao disfarcada de lucros (tributada como dividendos com IRRF 27,5%).

### 3.4. CONSTATACAO IV — MICROEMPREENDEDORES INDIVIDUAIS ACIMA DO TETO

**Situacao verificada:** **32 (trinta e dois) fornecedores enquadrados como MEI** com pagamentos anualizados projetados superiores ao teto legal de **R$ 81.000,00/ano** (LC 123/2006, art. 18-A, § 1).

**Casos mais relevantes:** 6 (seis) fornecedores recebem entre **R$ 67.000 e R$ 76.000 em 5 meses** (volume anualizado entre R$ 160.000 e R$ 184.000) — superior ao dobro do teto MEI.

**Implicacao juridica:** A LOCAR, como **contratante**, pode ser solidariamente responsavel se for caracterizada:

- **Terceirizacao ilicita** (Sumula 331 do TST);
- **PJ disfarcada de PF** (pejotizacao - art. 129, Lei 11.196/2005);
- **Vinculo empregaticio** se houver pessoalidade, subordinacao e habitualidade (CLT art. 3).

**Recomendacoes tecnicas:**

- Notificar os MEIs sobre obrigacao de **desenquadramento** (Resolucao CGSN 140/2018, art. 117);
- Reclassificar pagamentos como **prestacao de servico PJ** (PIS+COFINS+CSLL 4,65% + IRRF 1,5%) ou **autonomo PF** (IRRF tabela + INSS 11%);
- Manter contratos de prestacao de servico **com clausulas que afastem vinculo empregaticio**.

### 3.5. CONSTATACAO V — RETENCOES NA FONTE NAO RECOLHIDAS

**Situacao verificada:** A LOCAR, como **fonte pagadora** de servicos a pessoas juridicas e fisicas, deveria ter retido tributos na fonte:

| Categoria | Tributos devidos | Aliquota | Estimativa 5 meses |
|---|---|:---:|---:|
| Pagamentos a PJ (servicos) | PIS+COFINS+CSLL+IRRF | 6,15% | R$ 456.552,83 |
| Pagamentos a PF (autonomos) | IRRF+INSS | ate ~27,5% | R$ 32.164,40 |
| **TOTAL ESTIMADO** | | | **R$ 488.717,23** |

**Fundamentos legais:**

- **IN RFB 1.234/2012, art. 2** — retencoes PIS+COFINS+CSLL+IRRF sobre servicos PJ;
- **Lei 10.833/2003, art. 30** — retencao para servicos profissionais;
- **Lei 8.212/1991, art. 31** — INSS retido em servicos prestados por PF.

**Codigos de DARF aplicaveis:**

- **1708** — PIS+COFINS+CSLL+IRRF servicos PJ
- **0588** — IRRF servico PF autonomo
- **2631** — CSLL retida
- **0204** — Denuncia espontanea (art. 138 CTN)

**Implicacao penal-tributaria:** O nao recolhimento configura **infracao tributaria** (Lei 8.137/90), sujeitando a empresa a:

- Multa de oficio de **75% a 150%** sobre o tributo devido;
- Juros SELIC sobre o periodo;
- Possivel **representacao fiscal para fins penais** se houver dolo de sonegacao (art. 1, Lei 8.137/90).

**Recomendacao urgente:** Apurar e recolher as retencoes via **DARFs retroativos sob denuncia espontanea** (art. 138 CTN, codigo 0204), o que **afasta a multa de oficio** mas mantem juros SELIC.

### 3.6. CONSTATACAO VI — PAGAMENTOS APOS BAIXA DO CNPJ

**Situacao verificada:** **17 (dezessete) transacoes** efetuadas a CNPJs ja **BAIXADOS** na Receita Federal no momento do pagamento.

**Caso mais critico:**

- **Fornecedor:** PERCIVAL DIAS DA SILVA — CNPJ 63.567.345/0001-41
- **Situacao:** BAIXADO em 11/03/2026
- **Pagamentos posteriores:** 17 transacoes
- **Volume:** R$ 35.626,89
- **Defasagem maxima:** 63 dias apos a baixa

**Implicacoes graves:**

1. Pagamentos a CNPJ baixado podem caracterizar **simulacao** (art. 167, § 1, II, do CC) ou **fraude contra credores** (art. 159 do CC);
2. Os valores podem ser **glosados** como despesa dedutivel pelo Fisco (art. 311 do RIR/2018);
3. Em caso de notas fiscais emitidas apos a baixa, ha **emissao indevida de documento fiscal** (Lei 8.137/90);
4. Possivel caracterizacao de **lavagem de dinheiro** (Lei 9.613/98).

**Recomendacoes:**

a) Investigar a natureza dos pagamentos (servico efetivo? mutuo? pagamento ao CPF do ex-MEI?);
b) Caso confirmada prestacao de servico, reclassificar como **autonomo PF** com retencao na fonte;
c) Caso nao confirmada, **estornar lancamentos contabeis** e considerar comunicacao ao COAF (Lei 9.613/98).

## 4. Ressalvas Tecnicas

a) **Identificacao de partes relacionadas LOCAR LOCADORA e LOCAR MAQUINAS:** A confirmacao dos CNPJs depende de consulta complementar (truncamento do nome no OFX impede identificacao automatica).

b) **Apuracao precisa de retencoes:** Os valores estimados de R$ 488.717,23 tem por base aliquotas padrao. A apuracao exata depende da **natureza efetiva dos servicos prestados**, conferida via cotejamento com **notas fiscais de servico** correspondentes.

c) **Volume anualizado projetado:** O calculo de R$ 187.342.747,68 e projecao linear baseada em 4,5 meses. Pode haver sazonalidade nao capturada.

d) **Movimentacao com socio Renato Costa (R$ 8,25M):** Sem acesso a contratos de mutuo, atas de distribuicao ou folha de pagamento, nao foi possivel classificar definitivamente cada transacao individual.

## 5. Recomendacoes Formais com Prazos

| # | Acao | Prazo | Risco se nao executar |
|:---:|---|:---:|---|
| 1 | Apurar e recolher retencoes via denuncia espontanea | **30 dias** | Multa 75-150% + juros |
| 2 | Investigar pagamentos pos-baixa e estornar se aplicavel | **30 dias** | Glosa fiscal + risco penal |
| 3 | Implantar controle de retencoes na fonte | **30 dias** | Recorrencia das infracoes |
| 4 | Avaliar desenquadramento retroativo do regime EPP | **60 dias** | Auto de infracao RFB |
| 5 | Notificar MEIs sobre desenquadramento | **60 dias** | Responsabilidade solidaria |
| 6 | Documentar lastro contratual partes relacionadas | **90 dias** | Glosa de despesas + IRRF dividendos |
| 7 | Promover aumento de capital social | **120 dias** | Desconsideracao PJ |

## 6. Conclusao

Diante das constatacoes apresentadas, recomenda-se **PROVIDENCIAS IMEDIATAS** por parte da administracao da LOCAR TRANSPORTE DE BOVINOS LTDA para regularizar as questoes tributarias e contabeis identificadas.

A nao adocao das medidas recomendadas pode resultar em **autuacao fiscal substancial** estimada em **milhoes de reais** (considerando tributos devidos pelo regime correto + multas de oficio + juros).

Esta Carta de Constatacao tem **natureza tecnica e nao acusatoria**, sendo destinada exclusivamente a orientar a administracao da empresa quanto a aderencia normativa.

Permanecemos a disposicao para esclarecimentos e para acompanhar a regularizacao das pendencias identificadas.

Atenciosamente,

\\

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

## Referencias Normativas

- **Lei Complementar 123/2006** (Simples Nacional / EPP)
- **Lei 8.137/1990** (Crimes contra a ordem tributaria)
- **Lei 9.430/1996** (Multas e juros)
- **Lei 9.613/1998** (Lavagem de dinheiro / COAF)
- **Lei 10.833/2003** (Retencao PIS+COFINS+CSLL)
- **Lei 11.196/2005, art. 129** (Pejotizacao)
- **Lei 8.212/1991** (INSS)
- **IN RFB 1.234/2012** (Retencoes na fonte)
- **IN RFB 2.119/2022** (Cartao CNPJ)
- **Resolucao CGSN 140/2018** (MEI)
- **CPC 05 R1** (Partes Relacionadas)
- **NBC TA 230, 240, 320** (Normas de Auditoria)
- **CC arts. 50, 159, 167** (Desconsideracao PJ, Fraude, Simulacao)
- **CTN art. 135, 138** (Responsabilidade tributaria, Denuncia espontanea)
- **RIR/2018 arts. 311, 464** (Despesas e dividendos)
- **Sumula 331 TST** (Terceirizacao)

---

*Documento gerado em {hoje} pelo sistema OrgConc/OrgNeural2 v0.5.0. Confira o conteudo antes de assinar.*
"""


# ═══════════════════════════════════════════════════════════════════════
# HTML / PDF rendering
# ═══════════════════════════════════════════════════════════════════════


def _css_papel_timbrado() -> str:
    return """
@page {
  size: A4;
  margin: 22mm 18mm 22mm 18mm;
  @bottom-right { content: "Pagina " counter(page) " de " counter(pages); font-size: 9px; color: #6B7280; }
  @bottom-left { content: "ORGATEC · Documento Tecnico Formal"; font-size: 9px; color: #6B7280; }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DejaVu Serif', Georgia, serif; font-size: 11pt; color: #1a202c; line-height: 1.65; }

.hd {
  background: linear-gradient(135deg, #0F172A, #0B1B3D 45%, #0052FF);
  color: #fff;
  padding: 28px 32px;
  border-radius: 4px;
  margin-bottom: 28px;
  display: flex;
  align-items: center;
  gap: 22px;
}
.hd-text { flex: 1; }
.hd h1 { font-size: 24pt; font-family: 'DejaVu Serif', Georgia, serif; margin-bottom: 6px; letter-spacing: 1px; }
.hd .tag { font-size: 10pt; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.18em; }
.hd .meta { font-size: 9pt; opacity: 0.85; margin-top: 8px; }

h1 {
  font-size: 16pt;
  color: #0F172A;
  margin: 28px 0 12px;
  padding-bottom: 8px;
  border-bottom: 3px double #0052FF;
  text-align: center;
  font-family: 'DejaVu Serif', Georgia, serif;
}
h2 {
  font-size: 13pt;
  color: #0F172A;
  margin: 24px 0 10px;
  padding: 10px 14px;
  background: #F0F7FF;
  border-left: 4px solid #0052FF;
  font-family: 'DejaVu Serif', Georgia, serif;
}
h3 {
  font-size: 11pt;
  color: #0F172A;
  margin: 18px 0 8px;
  font-weight: 700;
}

p { margin-bottom: 10px; text-align: justify; }

table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0 18px;
  font-size: 10pt;
  font-family: 'DejaVu Sans', sans-serif;
}
th {
  background: linear-gradient(180deg, #0F172A, #1E3A8A);
  color: #fff;
  padding: 8px 12px;
  text-align: left;
  font-weight: 600;
}
td {
  padding: 7px 12px;
  border-bottom: 1px solid #E2E8F0;
}
tr:nth-child(even) td { background: #F8FAFC; }
strong { color: #0F172A; font-weight: 700; }
ul, ol { padding-left: 22px; margin-bottom: 12px; }
li { margin-bottom: 4px; }
hr { border: none; border-top: 1px solid #CBD5E1; margin: 18px 0; }
em { color: #64748B; font-size: 9pt; }
"""


def gerar_html(md_text: str, titulo_pagina: str, tag: str) -> str:
    import markdown as mdlib
    body = mdlib.markdown(md_text, extensions=["tables", "fenced_code"])
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    css = _css_papel_timbrado()
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>{titulo_pagina}</title><style>{css}</style></head>
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
    except Exception as exc:  # noqa: BLE001
        print(f"PDF failed: {exc}")
        return False


async def main_async():
    # Carta de Apresentacao
    print("Gerando CARTA DE APRESENTACAO EXECUTIVA...")
    md_apr = md_apresentacao()
    Path(f"{OUT_APR_BASE}.md").write_text(md_apr, encoding="utf-8")
    print(f"  MD:   {OUT_APR_BASE}.md")
    html_apr = gerar_html(md_apr, "Carta de Apresentacao - LOCAR", "Carta de Apresentacao Executiva · Entrega do Relatorio de Auditoria")
    Path(f"{OUT_APR_BASE}.html").write_text(html_apr, encoding="utf-8")
    print(f"  HTML: {OUT_APR_BASE}.html")
    if await gerar_pdf(html_apr, Path(f"{OUT_APR_BASE}.pdf")):
        print(f"  PDF:  {OUT_APR_BASE}.pdf")

    # Carta de Constatacao
    print()
    print("Gerando CARTA DE CONSTATACAO...")
    md_const = md_constatacao()
    Path(f"{OUT_CONST_BASE}.md").write_text(md_const, encoding="utf-8")
    print(f"  MD:   {OUT_CONST_BASE}.md")
    html_const = gerar_html(md_const, "Carta de Constatacao - LOCAR", "Carta de Constatacao · Memorando Tecnico-Juridico de Auditoria")
    Path(f"{OUT_CONST_BASE}.html").write_text(html_const, encoding="utf-8")
    print(f"  HTML: {OUT_CONST_BASE}.html")
    if await gerar_pdf(html_const, Path(f"{OUT_CONST_BASE}.pdf")):
        print(f"  PDF:  {OUT_CONST_BASE}.pdf")


if __name__ == "__main__":
    asyncio.run(main_async())
