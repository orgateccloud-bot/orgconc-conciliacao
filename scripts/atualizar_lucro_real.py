"""Regera Carta de Apresentacao + Carta de Constatacao + Relatorio Integrado
com a confirmacao de que LOCAR TRANSPORTE esta em LUCRO REAL (nao Simples).

Atualiza:
- Regime tributario atual: LUCRO REAL (confirmado pelo cliente)
- Historico: Excluida do Simples por Ato Administrativo RFB (2015-2018)
              + Exclusao voluntaria (2019)
- Constatacao I corrigida: empresa nao esta no Simples, mas em Lucro Real
- Novo achado: historico de exclusao administrativa pela RFB
- Recomendacoes ajustadas para regime Lucro Real (LALUR/SPED ECD/ECF)
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _logo_helper import html_logo_inline

OUT_APR = r"C:\Users\Veloso\Downloads\CARTA_APRESENTACAO_LOCAR"
OUT_CONST = r"C:\Users\Veloso\Downloads\CARTA_CONSTATACAO_LOCAR"


def _data_extenso() -> str:
    s = datetime.now().strftime("%d de %B de %Y")
    for en, pt in [("January", "janeiro"), ("February", "fevereiro"), ("March", "marco"),
                    ("April", "abril"), ("May", "maio"), ("June", "junho"),
                    ("July", "julho"), ("August", "agosto"), ("September", "setembro"),
                    ("October", "outubro"), ("November", "novembro"), ("December", "dezembro")]:
        s = s.replace(en, pt)
    return s


def _ref(prefixo: str) -> str:
    return f"{prefixo}-LOCAR-2026/05-{datetime.now().strftime('%d%m%H%M')}-v2"


# ═══════════════════════════════════════════════════════════════════════
# CARTA DE APRESENTACAO EXECUTIVA (v2 - Lucro Real confirmado)
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

**Assunto:** Entrega formal do Relatorio Integrado de Auditoria Bancaria, Carta de Constatacao e documentacao tecnica complementar. **Versao revisada com confirmacao de regime tributario (LUCRO REAL).**

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
- **Lei 12.973/2014** — Tributacao da pessoa juridica em Lucro Real

## II. Objeto do Trabalho

Foi conduzida **auditoria bancaria forense** sobre os extratos da conta corrente n. **158083-3**, agencia 3333-2, mantida no **SICOOB - Banco Cooperativo do Brasil (Codigo 756)**, referente ao periodo de:

- **Inicio:** 01 de janeiro de 2026
- **Fim:** 14 de maio de 2026
- **Duracao:** 4,5 meses (5 extratos mensais analisados)
- **Total de transacoes:** 7.110 lancamentos
- **Movimentacao bruta:** R$ 70.253.530,38

### Regime Tributario Confirmado

| Dado | Valor |
|---|---|
| **Regime atual** | **LUCRO REAL** (confirmado pelo contribuinte) |
| Optante Simples Nacional | NAO (RFB Consulta Optantes em 27/05/2026) |
| Historico Simples 2019 | Excluida por opcao do contribuinte |
| **Historico Simples 2015-2018** | **EXCLUIDA POR ATO ADMINISTRATIVO RFB** |
| Compatibilidade volume/regime | **CORRETO** — Lucro Real e obrigatorio para receita bruta > R$ 78M/ano |

Documentos examinados:

- 2a Alteracao e Consolidacao Contratual (06/11/2024)
- Cartao CNPJ emitido em 07/11/2024 (Receita Federal)
- **Consulta Optantes Simples Nacional/SIMEI** (RFB, 27/05/2026)
- 5 extratos OFX da conta 158083-3 (jan-mai/2026)

## III. Procedimentos Aplicados

Foram executados **6 procedimentos** sequenciais, com automacao via sistema OrgConc/OrgNeural2 (versao 0.5.0):

1. **Parsing e validacao** dos arquivos OFX em formato SGML, incluindo conferencia de saldo (LEDGERBAL) contra fluxo apurado;
2. **Classificacao em cascata** das transacoes em 6 estagios (transferencia interna, CNPJ/CPF, NF-e, tarifa bancaria, tributo, contrato);
3. **Enriquecimento de contrapartes** via cruzamento com a base publica de CNPJs da Receita Federal (BrasilAPI, 616 CNPJs identificados);
4. **Aplicacao de detectores forenses** — Risk Score 0-100;
5. **Classificacao tributaria** em 12 categorias (Retencao PJ/PF, IOF, Juros, Tarifa, etc.);
6. **Cruzamento com dados cadastrais** + Consulta Optantes RFB.

## IV. Sumario Executivo dos Achados (Revisado)

| # | Achado | Materialidade |
|---|---|:---:|
| I | **Confirmacao de regime Lucro Real** — apropriado para movimentacao apurada | Informativo |
| II | **Historico de exclusao administrativa do Simples (2015-2018)** | **Alto** |
| III | Subcapitalizacao (capital R$ 400k vs giro R$ 187M/ano) | **Critico** |
| IV | Movimentacao com partes relacionadas sem lastro contratual claro | **Alto** |
| V | 32 fornecedores enquadrados como MEI com volume superior ao teto | **Alto** |
| VI | Retencoes na fonte nao recolhidas: **R$ 488.717,23 estimados em 5 meses** | **Critico** |
| VII | 17 pagamentos a CNPJ baixado (Percival Dias - R$ 35.626,89) | **Critico** |

O **detalhamento juridico-tecnico** de cada achado, com fundamentacao normativa, valores apurados e recomendacoes formais com prazos esta consolidado na **Carta de Constatacao v2** anexa.

## V. Documentos Entregues (Anexos)

Esta entrega contempla os seguintes anexos tecnicos:

### A. Apresentacao Executiva (1 pagina)
- `APRESENTACAO_EXECUTIVA_LOCAR.pdf` — sintese visual para reuniao de apresentacao

### B. Documento Tecnico-Juridico
- `CARTA_CONSTATACAO_LOCAR.pdf` — memorando formal com 7 constatacoes, ressalvas e recomendacoes (revisado com Lucro Real)

### C. Relatorio Integrado Completo
- `RELATORIO_INTEGRADO_LOCAR_v2.xlsx` — 11 abas com indice navegavel
- `RELATORIO_INTEGRADO_LOCAR_v2.pdf` — versao impressa
- `RELATORIO_INTEGRADO_LOCAR_v2.html` — versao web

### D. Relatorios Mensais (detalhe por mes)
- `AUDIT_LOCAR_158083-3_{{JAN,FEV,MAR,ABR,MAI}}_2026.{{xlsx,pdf,html,md}}`

### E. Perfil Cadastral
- `PERFIL_AUDITORIA_LOCAR.pdf`

### F. Auditoria Consolidada
- `AUDITORIA_CONSOLIDADA_158083-3_5MESES.{{xlsx,pdf,html,md}}`

### G. Mapeamento do Sistema
- `MAPEAMENTO_PROJETO_ORGCONC.pdf` — confirmacao de integridade do sistema utilizado

## VI. Obrigacoes Acessorias do Lucro Real (lembretes)

A LOCAR, como optante do regime de Lucro Real, esta sujeita a:

| Obrigacao | Periodicidade | Fundamento |
|---|---|---|
| **LALUR Digital** (Livro de Apuracao do Lucro Real) | Anual | IN RFB 1.422/2013 |
| **e-LALUR** (parte do SPED-ECF) | Anual | Lei 11.638/2007 |
| **SPED-ECD** (Escrituracao Contabil Digital) | Anual | IN RFB 1.420/2013 |
| **SPED-ECF** (Escrituracao Contabil Fiscal) | Anual | IN RFB 1.422/2013 |
| **DCTF mensal** | Mensal | IN RFB 2.005/2021 |
| **EFD-Contribuicoes** | Mensal | IN RFB 1.252/2012 |
| **DIRF** (Declaracao do Imposto Retido na Fonte) | Anual | IN RFB 2.005/2021 |
| **IRPJ trimestral** | Trimestral | Lei 9.430/96 |

## VII. Procedimentos para Esclarecimentos

Permanecemos a disposicao para:

- **Reuniao de apresentacao** dos achados (presencial ou videoconferencia);
- **Esclarecimentos tecnicos** sobre fundamentacao normativa;
- **Apoio na regularizacao** das pendencias identificadas;
- **Implantacao de controles** preventivos para evitar recorrencia;
- **Suporte a obrigacoes acessorias do Lucro Real**.

### Canal de contato:

- Email: orgatec1@hotmail.com
- Telefones: (62) 9 9294-9161 / (62) 3377-6815

Solicita-se confirmacao do recebimento desta entrega e dos anexos, preferencialmente em ate **5 dias uteis**.

## VIII. Recomendacao Final

Diante da materialidade dos achados, recomenda-se que a administracao da LOCAR TRANSPORTE DE BOVINOS LTDA convoque **reuniao tecnica urgente** com seu corpo juridico-contabil para deliberar sobre:

1. As acoes prioritarias detalhadas na Carta de Constatacao (especialmente as de prazo de 30 dias);
2. A constituicao de **provisao contabil** adequada para os passivos tributarios identificados (PIS+COFINS+CSLL+IRRF retidas na fonte);
3. A regularizacao das retencoes na fonte via **denuncia espontanea** (art. 138 do CTN), afastando a multa de oficio;
4. **Revisao do LALUR** quanto ao tratamento contabil de transacoes com partes relacionadas.

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

*Documento emitido em {hoje} · Sistema OrgConc/OrgNeural2 v0.5.0 · Versao 2.0 com correcoes apos confirmacao do regime tributario pelo cliente.*
"""


# ═══════════════════════════════════════════════════════════════════════
# CARTA DE CONSTATACAO (v2 - Lucro Real confirmado)
# ═══════════════════════════════════════════════════════════════════════


def md_constatacao() -> str:
    hoje = _data_extenso()
    ref = _ref("CONST")
    return f"""# CARTA DE CONSTATACAO

**Memorando Tecnico-Juridico de Auditoria Bancaria — Versao 2.0**

---

**De:** ORGATEC CONTABILIDADE E AUDITORIA LTDA

**Para:** LOCAR TRANSPORTE DE BOVINOS LTDA — CNPJ 05.509.396/0001-10
A/C: Sr. Renato Costa Esperidiao Junior — Socio Administrador

**Referencia:** {ref}

**Assunto:** Constatacoes formais de auditoria sobre movimentacao bancaria — Conta SICOOB 158083-3 / Periodo 01/01/2026 a 14/05/2026. **Versao revisada apos confirmacao de regime tributario (LUCRO REAL).**

**Local e Data:** Goiania-GO, {hoje}

---

## 1. Preambulo

Prezado Sr. Renato Costa Esperidiao Junior,

Em atendimento aos procedimentos de auditoria contabil-fiscal aplicaveis a **LOCAR TRANSPORTE DE BOVINOS LTDA** (CNPJ 05.509.396/0001-10), apresentamos formalmente as constatacoes identificadas na analise dos extratos da conta 158083-3 (SICOOB 756, Ag. 3333-2) referente ao periodo de **01/01 a 14/05/2026**.

A movimentacao bruta apurada totaliza **R$ 70.253.530,38** em **7.110 transacoes**. Foram identificadas e enriquecidas **616 contrapartes (CNPJs)** via base publica da Receita Federal.

**Esta versao 2.0 incorpora a confirmacao do contribuinte de que a empresa esta atualmente em regime de LUCRO REAL**, conforme apurado tambem na Consulta Optantes Simples Nacional/SIMEI da RFB (consulta em 27/05/2026).

## 2. Regime Tributario Confirmado

| Item | Valor |
|---|---|
| **Regime atual** | **LUCRO REAL** |
| Optante Simples Nacional | **NAO** (confirmado pela Consulta Optantes RFB) |
| Periodo de exclusao voluntaria | 2019 — Excluida por Opcao do Contribuinte |
| **Periodo de exclusao administrativa** | **2015-2018 — EXCLUIDA POR ATO RFB** |
| Compatibilidade com volume apurado | **CORRETO** — Lucro Real e obrigatorio acima de R$ 78M/ano (art. 257, II, RIR/2018) |

## 3. Constatacoes

### 3.1. CONSTATACAO I — HISTORICO DE EXCLUSAO ADMINISTRATIVA DO SIMPLES NACIONAL

**Situacao verificada:** A consulta RFB ao portal do Simples Nacional revelou que a empresa foi **excluida por Ato Administrativo praticado pela Receita Federal do Brasil** no periodo de **01/01/2015 a 31/12/2018**.

**Implicacao tecnica:** A exclusao por **Ato Administrativo** (e nao voluntaria) caracteriza-se quando a fiscalizacao identifica:

- Estouro de teto de receita bruta;
- Inadimplencia tributaria superior a 60 meses;
- Constituicao irregular ou simulacao societaria;
- Exercicio de atividade vedada ao Simples;
- Indicios de fraude detectados pela RFB.

**Implicacao juridica:** Esse historico pode:

- Caracterizar **antecedente fiscal desfavoravel** em fiscalizacoes futuras;
- Ser usado em **prova de dolo** em representacao fiscal penal (art. 1, Lei 8.137/90);
- Dificultar **renovacao de certidoes negativas** (CND, CRF);
- Bloquear **adesoes a parcelamentos especiais** (Refis, PRT, PERT).

**Recomendacao:** Solicitar a RFB o **historico completo do ato de exclusao** (DARF + processo administrativo) para avaliar se ha materia de questionamento judicial ou se ja transitou em julgado.

### 3.2. CONSTATACAO II — SUBCAPITALIZACAO SIGNIFICATIVA

**Situacao verificada:** O capital social integralizado e de **R$ 400.000,00**, enquanto o giro anual projetado e de **R$ 187.342.747,68**.

**Razao volume/capital:** **468:1**.

**Implicacao juridica:** Caracteriza-se situacao de **subcapitalizacao**, o que pode:

- Sinalizar incompatibilidade entre o capital social e a atividade efetiva;
- Caracterizar **simulacao societaria** (art. 167, § 1, II, do CC);
- Ensejar **desconsideracao da personalidade juridica** (CC art. 50, CTN art. 135);
- Em **Lucro Real**, prejudicar a deducao de juros sobre capital proprio (Lei 9.249/95, art. 9) por insuficiencia de patrimonio liquido.

**Recomendacao tecnica:** Promover **aumento de capital social** mediante alteracao contratual, OU manter **declaracao especifica** no LALUR / SPED-ECF.

### 3.3. CONSTATACAO III — PARTES RELACIONADAS NAO SEGREGADAS

**Situacao verificada:** Movimentacoes significativas com entidades vinculadas ao mesmo controlador (Renato Costa Esperidiao Jr):

| Parte Relacionada | Transacoes | Volume (R$) | Natureza |
|---|---:|---:|---|
| LOCAR LOCADORA E ??? (CNPJ a confirmar) | 73 | 6.733.631,85 | Recebimentos PIX MESMA TIT |
| LOCAR MAQUINAS E SERVICOS | 13 | 249.947,18 | Pagamentos / Recebimentos |
| RENATO COSTA ESPERIDIAO JR (PF) | 201 | 8.253.024,12 | Pro-labore / Dividendos / Mutuo |

**Implicacao normativa especifica para LUCRO REAL:**

- **CPC 05 R1** — obriga a divulgacao em notas explicativas das demonstracoes contabeis;
- **Lei 12.973/2014, arts. 22-24** — preco de transferencia em operacoes intercompany;
- **art. 464 do RIR/2018** — distribuicao disfarcada de lucros, sujeita a IRRF de 27,5%;
- **LALUR** — adicao obrigatoria de despesas com partes relacionadas que excedam valor normal de mercado.

**Recomendacao tecnica:**

- Documentar cada movimentacao com **lastro contratual**;
- Manter **livro de partes relacionadas** atualizado;
- Verificar adicoes/exclusoes obrigatorias no LALUR (Lei 12.973/2014);
- Avaliar se ha **distribuicao disfarcada** (tributada como dividendos com IRRF 27,5%).

### 3.4. CONSTATACAO IV — MICROEMPREENDEDORES INDIVIDUAIS ACIMA DO TETO

**Situacao verificada:** **32 (trinta e dois) fornecedores enquadrados como MEI** com pagamentos anualizados projetados superiores ao teto legal de **R$ 81.000,00/ano** (LC 123/2006, art. 18-A, § 1).

**Implicacao juridica:** A LOCAR, como contratante, pode ser solidariamente responsavel por:

- **Terceirizacao ilicita** (Sumula 331 do TST);
- **PJ disfarcada de PF** (pejotizacao, art. 129, Lei 11.196/2005);
- **Vinculo empregaticio** se houver pessoalidade, subordinacao e habitualidade (CLT art. 3).

**Em Lucro Real, ha adicional:** as despesas com prestadores MEI que sejam descaracterizadas podem gerar **adicao no LALUR** (despesa nao dedutivel) com **majoracao de IRPJ e CSLL**.

### 3.5. CONSTATACAO V — RETENCOES NA FONTE NAO RECOLHIDAS

**Situacao verificada:** A LOCAR, como fonte pagadora em **regime de Lucro Real**, e **responsavel tributaria** pela retencao na fonte de:

| Categoria | Tributos | Aliquota | Estimativa 5 meses |
|---|---|:---:|---:|
| Pagamentos a PJ (servicos) | PIS+COFINS+CSLL+IRRF | 6,15% | R$ 456.552,83 |
| Pagamentos a PF (autonomos) | IRRF+INSS | ate ~27,5% | R$ 32.164,40 |
| **TOTAL ESTIMADO** | | | **R$ 488.717,23** |

**Fundamentos legais (Lucro Real):**

- **IN RFB 1.234/2012, art. 2** — PIS+COFINS+CSLL+IRRF sobre servicos PJ;
- **Lei 10.833/2003, art. 30** — retencao para servicos profissionais;
- **Lei 8.212/1991, art. 31** — INSS retido em servicos prestados por PF.

**Codigos de DARF aplicaveis:**

- **1708** — PIS+COFINS+CSLL+IRRF servicos PJ
- **0588** — IRRF servico PF autonomo
- **2631** — CSLL retida
- **0204** — Denuncia espontanea (art. 138 CTN)

**Implicacao penal-tributaria:** O nao recolhimento configura **infracao** (Lei 8.137/90):

- Multa de oficio de **75% a 150%** sobre o tributo;
- Juros SELIC;
- Possivel **representacao fiscal para fins penais**.

**Implicacao adicional para Lucro Real:** A nao retencao **NAO afasta a deducao** da despesa, mas:

- A despesa **so e dedutivel quando paga** OU **incorrida** dependendo do regime de competencia;
- A obrigatoriedade da retencao e do **TOMADOR** (LOCAR), nao do prestador;
- Risco de **glosa em fiscalizacao** se sem comprovacao do recolhimento da retencao.

**Recomendacao urgente:** Apurar e recolher via **DARFs retroativos sob denuncia espontanea** (art. 138 CTN, codigo 0204), afastando a multa de oficio.

### 3.6. CONSTATACAO VI — PAGAMENTOS APOS BAIXA DO CNPJ

**Situacao verificada:** **17 transacoes** efetuadas a CNPJs ja **BAIXADOS** na RFB no momento do pagamento.

**Caso mais critico:**

- **Fornecedor:** PERCIVAL DIAS DA SILVA — CNPJ 63.567.345/0001-41
- **Situacao:** BAIXADO em 11/03/2026
- **Pagamentos posteriores:** 17 transacoes
- **Volume:** R$ 35.626,89
- **Defasagem maxima:** 63 dias

**Implicacoes para Lucro Real:**

- A despesa correspondente pode ser **GLOSADA na fiscalizacao** (art. 311 do RIR/2018);
- Em LALUR, deve haver **adicao automatica** das despesas indedutiveis;
- Risco de **simulacao** (art. 167, § 1, II, do CC) ou **fraude** (art. 159 do CC);
- Possivel **lavagem de dinheiro** (Lei 9.613/98) — comunicar ao COAF se aplicavel.

**Recomendacoes:**

a) Investigar a natureza dos pagamentos (servico real? mutuo? CPF do ex-MEI?);
b) Se servico, reclassificar como **autonomo PF** (IRRF + INSS);
c) Caso nao confirmado, **estornar lancamentos** e **adicionar no LALUR** como despesa indedutivel.

### 3.7. CONSTATACAO VII — VOLUME COMPATIVEL COM LUCRO REAL (CONFIRMACAO POSITIVA)

**Situacao verificada:** A movimentacao anualizada projetada (**R$ 187.342.747,68**) **excede largamente o limite obrigatorio de Lucro Real** (R$ 78.000.000,00/ano, art. 257, II, do RIR/2018).

**Implicacao:** A opcao pelo Lucro Real esta **CORRETA** e **OBRIGATORIA** para essa empresa.

**Verificacao recomendada:**

- Confirmar que a **EFD-Contribuicoes** esta sendo entregue mensalmente;
- Confirmar que o **LALUR Digital** (SPED-ECF) esta sendo escriturado anualmente;
- Confirmar que a **DCTF** esta sendo entregue mensalmente sem multas por atraso;
- Verificar se ha **DIRF** sendo entregue anualmente refletindo as retencoes.

## 4. Ressalvas Tecnicas

a) **Identificacao das partes relacionadas LOCAR LOCADORA e LOCAR MAQUINAS** depende de consulta complementar (CNPJ truncado no OFX).

b) **Apuracao precisa de retencoes (R$ 488.717,23)** depende de notas fiscais de servico para confirmar a natureza dos pagamentos.

c) **Movimentacao com socio Renato Costa (R$ 8,25M)** depende de acesso a contratos de mutuo, atas de distribuicao e folha de pagamento.

d) **Historico de exclusao administrativa do Simples (2015-2018)** depende de acesso ao processo administrativo da RFB para avaliacao do mérito.

## 5. Recomendacoes Formais com Prazos

| # | Acao | Prazo | Risco se nao executar |
|:---:|---|:---:|---|
| 1 | Apurar e recolher retencoes via denuncia espontanea | **30 dias** | Multa 75-150% + juros |
| 2 | Investigar pagamentos pos-baixa e estornar se aplicavel | **30 dias** | Glosa LALUR + risco penal |
| 3 | Implantar controle de retencoes na fonte | **30 dias** | Recorrencia das infracoes |
| 4 | Solicitar processo administrativo da exclusao 2015-2018 | **30 dias** | Antecedente fiscal pendente |
| 5 | Notificar MEIs sobre desenquadramento | **60 dias** | Responsabilidade solidaria + glosa LALUR |
| 6 | Documentar lastro contratual partes relacionadas | **90 dias** | Adicoes obrigatorias no LALUR |
| 7 | Promover aumento de capital social | **120 dias** | Desconsideracao PJ + perda de JCP |
| 8 | Conferir obrigacoes acessorias do Lucro Real | **30 dias** | Multas por DCTF/EFD/SPED em atraso |

## 6. Conclusao

A LOCAR TRANSPORTE DE BOVINOS LTDA, em regime de **Lucro Real**, apresenta enquadramento tributario **adequado para sua movimentacao real** (R$ 187M/ano). Contudo, os achados de auditoria revelam **pendencias materiais** que exigem regularizacao imediata, totalizando potencial passivo tributario na ordem de **R$ 500.000,00+** considerando apenas as retencoes nao recolhidas, sem incluir multas, juros e eventuais adicoes obrigatorias no LALUR.

Recomenda-se **PROVIDENCIAS IMEDIATAS** para evitar autuacao fiscal substancial e proteger o **antecedente fiscal** da empresa, ja sensivel devido ao historico de exclusao administrativa de 2015-2018.

Permanecemos a disposicao para esclarecimentos e para acompanhar a regularizacao das pendencias identificadas.

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

## Referencias Normativas (atualizadas)

- **Lei Complementar 123/2006** (Simples Nacional / EPP — historico)
- **Lei 12.973/2014** (Tributacao de PJ em Lucro Real)
- **Lei 9.430/1996** (IRPJ + multas e juros)
- **Lei 9.249/1995** (Juros sobre Capital Proprio)
- **RIR/2018, art. 257, II** (obrigatoriedade do Lucro Real > R$ 78M)
- **RIR/2018, art. 311** (despesas glosadas)
- **RIR/2018, art. 464** (distribuicao disfarcada de lucros)
- **Lei 8.137/1990** (Crimes contra a ordem tributaria)
- **Lei 9.613/1998** (Lavagem de dinheiro / COAF)
- **Lei 10.833/2003** (Retencao PIS+COFINS+CSLL)
- **Lei 8.212/1991** (INSS)
- **IN RFB 1.234/2012** (Retencoes na fonte)
- **IN RFB 1.420/2013** (SPED-ECD)
- **IN RFB 1.422/2013** (SPED-ECF + LALUR Digital)
- **IN RFB 2.005/2021** (DCTF + DIRF)
- **IN RFB 2.119/2022** (Cartao CNPJ)
- **CPC 05 R1** (Partes Relacionadas)
- **NBC TA 230, 240, 320** (Normas de Auditoria)
- **CC arts. 50, 159, 167** (Desconsideracao PJ, Fraude, Simulacao)
- **CTN art. 135, 138** (Responsabilidade tributaria, Denuncia espontanea)
- **Sumula 331 TST** (Terceirizacao)

---

*Documento gerado em {hoje} pelo sistema OrgConc/OrgNeural2 v0.5.0 — versao 2.0 com confirmacao de regime Lucro Real.*
"""


# ═══════════════════════════════════════════════════════════════════════
# HTML / PDF rendering (mesmo papel timbrado das versoes anteriores)
# ═══════════════════════════════════════════════════════════════════════


def _css_papel() -> str:
    return """
@page {
  size: A4;
  margin: 22mm 18mm 22mm 18mm;
  @bottom-right { content: "Pagina " counter(page) " de " counter(pages); font-size: 9px; color: #6B7280; }
  @bottom-left { content: "ORGATEC · Documento Tecnico Formal v2.0"; font-size: 9px; color: #6B7280; }
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
    # Apresentacao
    print("Gerando CARTA DE APRESENTACAO (v2 - Lucro Real)...")
    md = md_apresentacao()
    Path(f"{OUT_APR}.md").write_text(md, encoding="utf-8")
    print(f"  MD:   {OUT_APR}.md")
    html = gerar_html(md, "Carta de Apresentacao v2 - LOCAR",
                     "Carta de Apresentacao Executiva · Versao 2.0 (Lucro Real confirmado)")
    Path(f"{OUT_APR}.html").write_text(html, encoding="utf-8")
    print(f"  HTML: {OUT_APR}.html")
    if await gerar_pdf(html, Path(f"{OUT_APR}.pdf")):
        print(f"  PDF:  {OUT_APR}.pdf")

    print()
    # Constatacao
    print("Gerando CARTA DE CONSTATACAO (v2 - Lucro Real)...")
    md = md_constatacao()
    Path(f"{OUT_CONST}.md").write_text(md, encoding="utf-8")
    print(f"  MD:   {OUT_CONST}.md")
    html = gerar_html(md, "Carta de Constatacao v2 - LOCAR",
                     "Carta de Constatacao · Memorando Tecnico-Juridico v2.0 (Lucro Real)")
    Path(f"{OUT_CONST}.html").write_text(html, encoding="utf-8")
    print(f"  HTML: {OUT_CONST}.html")
    if await gerar_pdf(html, Path(f"{OUT_CONST}.pdf")):
        print(f"  PDF:  {OUT_CONST}.pdf")


if __name__ == "__main__":
    asyncio.run(main_async())
