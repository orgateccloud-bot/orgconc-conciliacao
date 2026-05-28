"""Gera PLANEJAMENTO DE INTEGRACAO FISCAL ao projeto OrgConc/OrgNeural2.

Documenta como integrar permanentemente ao core do projeto:
- Modulo de processamento XML NF-e/CT-e (api/matchers/xml_fiscal.py)
- Modelos DB (NfeRecebida, CteEmitido, ConformidadeFiscal)
- Endpoint /matchers/cruzar_nfe_ofx
- UI: pagina /conformidade-fiscal
- Sprints de implementacao

Saidas: PDF + HTML + MD
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _logo_helper import html_logo_inline

OUT_BASE = r"C:\Users\Veloso\Downloads\PLANEJAMENTO_INTEGRACAO_FISCAL"


def md():
    return f"""# PLANEJAMENTO DE INTEGRACAO FISCAL

**Modulo de Cruzamento NF-e/CT-e/OFX no OrgConc + OrgNeural2**

---

**Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M')}
**Sistema:** OrgConc v0.5.0 + OrgNeural2 (motor matchers 6 estagios)
**Cliente piloto:** LOCAR TRANSPORTE DE BOVINOS LTDA (CNPJ 05.509.396/0001-10)
**Repositorio:** branch main · sincronizado origin

---

## 1. Contexto e Motivacao

Durante a auditoria da LOCAR, foram desenvolvidos **scripts isolados** em `scripts/` que processam XMLs de NF-e e CT-e cruzando com transacoes OFX. Os scripts ja produzem achados criticos:

- **REDE FROTA SOLUTIONS:** R$ 8,84M/ano em pagamentos sem NF-e -> R$ 3M/ano risco tributario
- **5 MEIs caminhoneiros:** R$ 1,05M/ano sem CT-e de subcontratacao
- **3.045 CT-es** + **5.031 NF-es** + 7.110 transacoes OFX processados sem persistencia

**Problema:** essas analises sao geradas via scripts ad-hoc, sem armazenamento no banco, sem integracao ao app, sem reusabilidade para outros clientes.

**Objetivo:** **internalizar o modulo fiscal** ao core do OrgConc como funcionalidade permanente.

## 2. Arquitetura Proposta

### 2.1. Diagrama de fluxo

```
┌────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                            │
│  /conformidade-fiscal → Upload ZIP NFe + ZIP CTe + OFX             │
└─────────────────────┬──────────────────────────────────────────────┘
                      │  POST /fiscal/processar
                      ▼
┌────────────────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI)                                │
│  api/routers/fiscal.py — orquestrador                              │
│    ├─→ api/matchers/xml_fiscal.py — parser unificado NF-e+CT-e    │
│    ├─→ api/matchers/cruzamento_fiscal.py — matching fiscal-banco   │
│    ├─→ api/matchers/conformidade.py — score conformidade           │
│    └─→ services/db_persistence.py — salva NfeRecebida/CteEmitido   │
└─────────────────────┬──────────────────────────────────────────────┘
                      │  ORM async
                      ▼
┌────────────────────────────────────────────────────────────────────┐
│                   POSTGRESQL (Supabase)                            │
│  Novas tabelas:                                                    │
│    - documento_fiscal (NF-e + CT-e unificados)                     │
│    - cruzamento_fiscal (doc x transacao)                           │
│    - conformidade_fornecedor (% por CNPJ)                          │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2. Novos componentes

#### Backend (`api/matchers/`)

| Arquivo | Funcao | Linhas estimadas |
|---|---|---:|
| `xml_fiscal.py` | Parser unificado NF-e + CT-e + NFS-e (com namespace abstraction) | ~400 |
| `cruzamento_fiscal.py` | Cruza documentos com transacoes OFX (tolerancia valor+data+CNPJ) | ~300 |
| `conformidade.py` | Calcula score 0-100 por fornecedor + flags (REDE_FROTA, MEI_SEM_CTE) | ~200 |
| `tributario.py` | Estimativa de tributos adicionais (IRPJ+CSLL sobre despesa indedutivel) | ~150 |

#### Routers (`api/routers/`)

| Arquivo | Endpoints | Funcao |
|---|---|---|
| `fiscal.py` | `POST /fiscal/processar` | Upload ZIP NFe + ZIP CTe + OFX → processa cascata |
| | `GET /fiscal/conformidade/{{cliente_id}}` | Score consolidado por cliente |
| | `GET /fiscal/gap/{{cliente_id}}` | Transacoes sem NF (gaps) |
| | `GET /fiscal/risco-tributario/{{cliente_id}}` | Estimativa de risco em Lucro Real |

#### Modelos DB (`api/db/models.py`)

```python
class DocumentoFiscal(Base):
    __tablename__ = "documento_fiscal"
    id: UUID PK
    cliente_id: FK clientes.id
    tipo: str  # "NF-e" | "CT-e" | "NFS-e"
    chave: str(44)  # chave de acesso unica
    numero: str
    data_emissao: date
    emit_cnpj: str(14)
    emit_nome: str
    dest_cnpj: str(14)
    dest_nome: str
    valor_total: Numeric(15,2)
    valor_icms: Numeric(15,2)
    valor_pis: Numeric(15,2)
    valor_cofins: Numeric(15,2)
    modelo: str(2)  # "55", "57", "65", etc
    uf_emit: str(2)
    xml_path: str  # caminho do XML no storage
    criado_em: timestamptz

class CruzamentoFiscal(Base):
    __tablename__ = "cruzamento_fiscal"
    id: UUID PK
    documento_id: FK documento_fiscal.id
    transacao_id: FK transacoes.id (nullable - SEM_PAGAMENTO)
    status: str  # "CASADO" | "VALOR_DIVERGENTE" | "SEM_PAGAMENTO" | "SEM_NF"
    diferenca_valor: Numeric(15,2)
    diferenca_dias: int
    criado_em: timestamptz

class ConformidadeFornecedor(Base):
    __tablename__ = "conformidade_fornecedor"
    id: UUID PK
    cliente_id: FK clientes.id
    cnpj_fornecedor: str(14)
    razao_social: str
    periodo_inicio: date
    periodo_fim: date
    volume_pago: Numeric(15,2)
    volume_nf: Numeric(15,2)
    conformidade_pct: Numeric(5,2)  # 0 a 100+
    n_pagamentos: int
    n_nfes: int
    risco_classe: str  # "BAIXO" | "MEDIO" | "ALTO" | "CRITICO"
    risco_tributario_anual: Numeric(15,2)
    atualizado_em: timestamptz
```

#### Frontend (`orgconc-react/src/pages/`)

| Pagina | Rota | Funcionalidades |
|---|---|---|
| `ConformidadeFiscalPage.tsx` | `/conformidade-fiscal` | Upload + status em real-time + dashboard de gaps |
| `GapsFiscaisPage.tsx` | `/gaps-fiscais` | Lista de fornecedores com gap fiscal + filtros |
| `RiscoTributarioPage.tsx` | `/risco-tributario` | Estimativa IRPJ+CSLL adicional + simulador |

## 3. Sprints de Implementacao

### Sprint 1 — Backend Fiscal Core (5 dias)

**Objetivo:** infraestrutura backend para processar e armazenar documentos fiscais.

**Entregas:**

1. `api/matchers/xml_fiscal.py` (parser unificado)
2. `api/db/models.py`: 3 tabelas novas (DocumentoFiscal, CruzamentoFiscal, ConformidadeFornecedor)
3. `api/routers/fiscal.py` com 4 endpoints
4. `api/services/db_persistence.py`: funcoes `salvar_documentos_fiscais()` + `salvar_cruzamento()`
5. SQL de migracao manual: 3 CREATE TABLE
6. Tests: `tests/test_xml_fiscal.py` (parsing + cruzamento)

**Critério de aceite:** Upload de 1 ZIP NF-e + 1 ZIP CT-e + 1 OFX retorna disposicoes persistidas no DB.

---

### Sprint 2 — Conformidade Fiscal + Risco Tributario (3 dias)

**Objetivo:** logica de scoring e classificacao de riscos.

**Entregas:**

1. `api/matchers/conformidade.py`:
   - `calcular_conformidade_fornecedor()` retorna pct (0-100+)
   - `classificar_risco()` retorna CRITICO/ALTO/MEDIO/BAIXO
   - Deteccao de flags: `REDE_FROTA_TYPE` (cartao corporativo sem NF), `MEI_SEM_CTE`, `PARTE_RELACIONADA`
2. `api/matchers/tributario.py`:
   - `estimar_risco_tributario_anual()` para Lucro Real (IRPJ 25% + CSLL 9%)
   - `estimar_retencoes_nao_recolhidas()` (PIS/COFINS/CSLL/IRRF)
3. Endpoint `GET /fiscal/risco-tributario/{{cliente_id}}` retorna json com indicadores agregados
4. Tests: cenarios CRITICO/ALTO/MEDIO/BAIXO + flags especificos

**Critério de aceite:** A LOCAR retorna 32 fornecedores classificados + REDE FROTA como CRITICO com R$ 3M/ano de risco IRPJ+CSLL.

---

### Sprint 3 — UI Conformidade Fiscal (4 dias)

**Objetivo:** interface React para os contadores explorarem os gaps.

**Entregas:**

1. `pages/ConformidadeFiscalPage.tsx`:
   - Card grande com **Score Geral de Conformidade** (0-100)
   - 4 KPIs: Volume com NF / Sem NF / Risco Tributario / % Casamento
   - Botao "Iniciar Cruzamento" abre dialog de upload (NF-e ZIP + CT-e ZIP + OFX)
   - Tabela "Top fornecedores com gap" (red flags)
2. `pages/GapsFiscaisPage.tsx`:
   - Filtros: Cliente, Periodo, Classe de Risco
   - Tabela paginada com 5.000+ linhas
   - Acao "Gerar relatorio PDF" por cliente
3. `pages/RiscoTributarioPage.tsx`:
   - Simulador: "Se eu cadastrar NF-e para fornecedor X, quanto economizo?"
   - Grafico de evolucao mensal do gap fiscal
4. `components/Sidebar.tsx`: nova categoria "FISCAL" com 3 itens
5. `lib/api.ts`: 4 novas funcoes (`fiscalProcessar`, `fiscalConformidade`, `fiscalGap`, `fiscalRiscoTributario`)

**Critério de aceite:** Contador faz upload, ve dashboard, exporta PDF, navega entre paginas.

---

### Sprint 4 — Automacao + Notificacoes (3 dias)

**Objetivo:** automatizar deteccao mensal de gaps + alertas.

**Entregas:**

1. **Job assincrono** (Celery ou cron simples): mensalmente cruza NF/CT/OFX automaticamente
2. **Webhooks/Notificacoes**: quando um fornecedor passa para CRITICO, envia email + grava em `audit_events`
3. **Integracao SEFAZ-NSU** (futuro): API para baixar NF-es automaticamente via Nota Source/Distribuicao DFe
4. **Cache CNPJ + integracao RFB**: ja existe via `cnpj_enricher.py`, integrar a fluxo fiscal

**Critério de aceite:** Sistema detecta automaticamente novo gap fiscal e notifica responsavel.

---

### Sprint 5 — Relatorios + Templates de Carta Automatizados (4 dias)

**Objetivo:** gerar Carta de Constatacao automaticamente a partir do banco.

**Entregas:**

1. `api/services/carta_constatacao.py`:
   - Template Jinja2 da Carta com 8 Constatacoes parametrizaveis
   - Dados extraidos de `conformidade_fornecedor` + `transacao_disposicao`
2. Endpoint `POST /fiscal/gerar-carta/{{cliente_id}}` retorna PDF da Carta
3. Endpoint `POST /fiscal/gerar-relatorio-integrado/{{cliente_id}}` retorna XLSX com 14 abas
4. **Versionamento de cartas:** cada geracao salva nova versao em `carta_versoes` (audit trail)
5. UI: pagina `/cartas` lista cartas geradas por cliente + reemitir

**Critério de aceite:** Cliente novo gera Carta + Relatorio em 30 segundos.

## 4. Cronograma Consolidado

| Sprint | Dias | Acumulado | Resultado |
|:------:|:----:|:--------:|---|
| 1 | 5 | 5 | Backend processa XMLs |
| 2 | 3 | 8 | Score de conformidade |
| 3 | 4 | 12 | UI funcional |
| 4 | 3 | 15 | Automacao mensal |
| 5 | 4 | 19 | Cartas auto-geradas |

**Esforco total estimado:** **19 dias uteis (~1 mes de trabalho dedicado)**

## 5. Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|---|:---:|:---:|---|
| Volume grande de XMLs trava o request | Media | Alto | Processamento async + filas (Celery/RQ) |
| NFS-e municipal tem schema diferente | Alta | Medio | Modulo dedicado `nfse_municipal.py` (fase 2) |
| Cruzamento CNPJ truncado no OFX | Confirmada | Alto | Manter fuzzy match por nome (ja existe) |
| Storage de XMLs cresce muito | Alta | Medio | Storage S3/Supabase Storage + compressao gzip |
| Falsos positivos em conformidade | Media | Medio | Janela de cruzamento ampliada (60 dias) + agrupamento de pagamentos |

## 6. Beneficios para o Negocio ORGATEC

### Atual (manual com scripts)
- Auditoria leva **2-3 dias por cliente**
- Cada cliente requer rodar 6+ scripts diferentes
- Cartas/Relatorios sao montados manualmente

### Pos-integracao
- Auditoria **automatizada em 30 segundos** apos upload
- **Score de conformidade fiscal** continuo (dashboard)
- **Cartas de Constatacao geradas automaticamente** com dados versionados
- **Detecção precoce** de gaps mensais (job automatico)
- **Escalavel para 100+ clientes** (multitenancy via `org_id` ja implementado)

### Valor monetario potencial

Considerando a LOCAR como piloto:
- Achados: **R$ 3,36M/ano** de risco tributario detectado
- Honorarios de regularizacao tributaria: **~10-15%** sobre o passivo evitado
- Valor potencial para ORGATEC por cliente similar: **R$ 336k-504k/ano**

Com 10 clientes similares: **R$ 3,3M-5M/ano em honorarios**.

## 7. Manutencao e Evolucao Futura

### Backlog pos-MVP

- **Integracao SEFAZ-NSU** (download automatico NF-e/CT-e)
- **NFS-e Municipal** (modelo proprio, integrar com Anapolis/Goiania/SP/RJ)
- **Sintegra / SPED** (cruzar com escrituracao oficial)
- **Machine Learning** para detectar padroes anomalos (pre-treinamento com auditorias antigas)
- **API publica** para clientes consumirem score de conformidade
- **App Mobile** (React Native) para contadores verem alertas em tempo real

## 8. Aprovacao e Proximo Passo

Para iniciar a implementacao:

1. **Aprovar este plano** (gestao ORGATEC)
2. **Criar branch** `feature/integracao-fiscal` no repo
3. **Iniciar Sprint 1** (backend fiscal core)
4. **Code review** ao final de cada sprint
5. **Deploy em staging** apos Sprint 3
6. **Deploy em producao** apos Sprint 5 + smoke testing

---

*Plano elaborado pelo sistema OrgConc/OrgNeural2 v0.5.0. Esforco estimado em horas de desenvolvimento dedicado.*
"""


async def main_async():
    md_text = md()
    Path(f"{OUT_BASE}.md").write_text(md_text, encoding="utf-8")
    print(f"  MD:   {OUT_BASE}.md")

    import markdown as mdlib
    body = mdlib.markdown(md_text, extensions=["tables", "fenced_code"])
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    css = """
@page { size: A4 portrait; margin: 18mm 16mm 18mm 16mm;
  @bottom-right { content: "Pagina " counter(page) " de " counter(pages); font-size: 9px; color: #6B7280; }
  @bottom-left { content: "Plano de Integracao Fiscal · OrgConc v0.5.0"; font-size: 9px; color: #6B7280; }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10pt; color: #1a202c; line-height: 1.6; }
.hd { background: linear-gradient(135deg, #0F172A, #0B1B3D 45%, #0052FF); color: #fff;
      padding: 26px 32px; border-radius: 8px; margin-bottom: 24px; display: flex; align-items: center; gap: 22px; }
.hd-text { flex: 1; }
.hd h1 { font-size: 22pt; font-family: 'DejaVu Serif', Georgia, serif; }
.hd .tag { font-size: 10pt; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.18em; }
h1 { font-size: 16pt; color: #0F172A; margin: 26px 0 12px; padding-bottom: 8px; border-bottom: 2px solid #0052FF;
     font-family: 'DejaVu Serif', Georgia, serif; }
h2 { font-size: 13pt; color: #0F172A; margin: 22px 0 10px; padding: 8px 14px;
     background: linear-gradient(90deg, #F0F7FF, transparent); border-left: 4px solid #0052FF; }
h3 { font-size: 11pt; color: #0052FF; margin: 16px 0 6px; font-weight: 700; }
h4 { font-size: 10pt; color: #0F172A; margin: 12px 0 5px; font-weight: 700; }
p { margin-bottom: 8px; text-align: justify; }
table { width: 100%; border-collapse: collapse; margin: 10px 0 14px; font-size: 9pt;
        border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
th { background: linear-gradient(180deg, #0F172A, #1E3A8A); color: #fff;
     padding: 6px 9px; text-align: left; font-weight: 600; }
td { padding: 5px 9px; border-bottom: 1px solid #E2E8F0; }
tr:nth-child(even) td { background: #F8FAFC; }
strong { color: #0F172A; font-weight: 700; }
code { background: #F1F5F9; padding: 1px 5px; border-radius: 3px; color: #0052FF;
       font-family: 'DejaVu Sans Mono', Consolas, monospace; font-size: 8.5pt; }
pre { background: #0F172A; color: #DBEAFE; padding: 14px; border-radius: 6px;
      font-family: 'DejaVu Sans Mono', Consolas, monospace; font-size: 8.5pt;
      overflow-x: auto; margin: 12px 0; line-height: 1.4; }
pre code { background: transparent; color: inherit; padding: 0; }
ul, ol { padding-left: 24px; margin-bottom: 10px; }
li { margin-bottom: 4px; }
hr { border: none; border-top: 1px solid #CBD5E1; margin: 18px 0; }
em { color: #64748B; font-size: 9pt; }
"""
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>Plano de Integracao Fiscal · OrgConc</title><style>{css}</style></head>
<body>
<div class="hd">{html_logo_inline()}<div class="hd-text">
<h1>ORGATEC</h1>
<div class="tag">Plano Tecnico · Integracao Fiscal</div>
<div style="margin-top:8px;font-size:9pt;opacity:.85">OrgConc v0.5.0 + OrgNeural2 · Roadmap de 5 sprints · Gerado em {agora}</div>
</div></div>
{body}
</body></html>"""
    Path(f"{OUT_BASE}.html").write_text(html, encoding="utf-8")
    print(f"  HTML: {OUT_BASE}.html")

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html, wait_until="load")
            await page.pdf(
                path=f"{OUT_BASE}.pdf", format="A4",
                margin={"top": "18mm", "right": "16mm", "bottom": "18mm", "left": "16mm"},
                print_background=True,
            )
            await browser.close()
        print(f"  PDF:  {OUT_BASE}.pdf")
    except Exception as exc:
        print(f"PDF failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main_async())
