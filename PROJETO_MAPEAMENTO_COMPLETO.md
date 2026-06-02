# OrgConc — Mapeamento Completo de Módulos & Relatório de Pontuação

**Data:** 2026-06-02
**Projeto:** OrgConc (Conciliação Fiscal Bancária — FastAPI + React + Supabase/Postgres)
**Versão:** 0.5.0
**Branch:** `claude/peaceful-meninsky-511d61` (PR #50 — laudo forense + aba Auditoria Forense)
**Remapeamento anterior:** 2026-05-28 (6.4/10)

---

## SUMÁRIO EXECUTIVO

| Métrica | Valor | Status |
|---------|-------|--------|
| **Backend (Python)** | ~14.049 LOC · 9 subpacotes | ✅ Clean Architecture em camadas |
| **Frontend (React/TS)** | ~9.000 LOC src · 15 páginas | ✅ React 19 + shadcn/ui |
| **Endpoints HTTP** | 49 rotas em 15 routers | ✅ REST + auth JWT |
| **Matchers (domínio fiscal)** | 3.022 LOC · 16 arquivos | ✅ Diferencial do produto |
| **Testes Backend** | **446 testes** · cobertura 74% (bloqueante no CI) | ✅ Forte |
| **Testes Frontend** | ~10 unit (5 páginas) + 4 specs E2E | ⚠️ 10 páginas sem teste |
| **Observabilidade** | Prometheus `/metrics` + Sentry + log JSON | ✅ Implementado |
| **Deploy** | Railway (Docker multi-stage, React same-origin `/app`) | ✅ Seguro e automático |
| **CI/CD** | 4 jobs (test, security, frontend, e2e) + synthetic monitor | ✅ Lint ruff bloqueante |
| **Documentação** | README, DEPLOY, RUNBOOK, MONITORING, BACKUP, SCHEMA | ✅ Cobertura DevOps |
| **Pontuação Geral** | **7.6 / 10** | 🟢 Production-ready (falta staging) |

> **Evolução vs 2026-05-28:** +52% de LOC backend (9.250→14.049), 446 testes (+118), 4 dos 5 P0/P1 críticos resolvidos (deploy seguro, Railway automation, Prometheus, lint bloqueante). Nota geral 6.4 → **7.6**.

---

## 1. ARQUITETURA BACKEND — Análise Estrutural

### 1.1 Visão Geral (camadas)

```
┌──────────────────────────────────────────────────────────────┐
│ HTTP: routers/ (15 arquivos, 49 endpoints, 2.567 LOC)         │
│ ├─ fiscal.py (692) · conciliacao.py (458) · auth_routes (199) │
│ └─ metrics · guias · contratos · matchers · clientes · audit  │
└───────────────────────────────┬──────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────┐
│ Application: services/ (18 arq, 4.919 LOC)                    │
│ ├─ laudo_forense.py (1.909 ⚠) · excel.py (574)               │
│ ├─ carta_constatacao · conciliacao_llm · auth · ai_insights  │
│ └─ fiscal_persistence · audit · storage · logging            │
└───────┬──────────────────────────────────────────────┬───────┘
        ↓                                                ↓
┌────────────────────────────┐              ┌───────────────────┐
│ Domínio: matchers/ (3.022)  │              │ parsers/ (700)    │
│ ├─ cnpj_enricher (476)      │              │ ├─ anomalies (161)│
│ ├─ forensics (411)          │              │ ├─ pdf (137)      │
│ ├─ orquestrador (260)       │              │ └─ ofx · xml · csv│
│ └─ auditoria_forense · ...  │              └───────────────────┘
└──────────────┬──────────────┴───────────────────────┬─────────┘
               ↓                                        ↓
     ┌──────────────────────┐              ┌────────────────────────┐
     │ domain/ (385) + infra │              │ db/ (1.002 LOC)        │
     │ value objects, repos  │              │ models.py (16 entid.)  │
     └──────────────────────┘              │ metrics · audit · CRUD │
                                           └────────────┬───────────┘
                                                        ↓
                              ┌──────────────────────────────────────┐
                              │ core/ (986): config · prometheus      │
                              │ observability · llm_metrics · rate_lim │
                              └──────────────────────────────────────┘
```

### 1.2 Módulos Principais

| Módulo | LOC | Arq. | Responsabilidade | Pontuação |
|--------|-----|------|------------------|-----------|
| **core/** | 986 | 10 | Config, Prometheus, observability (Sentry), llm_metrics, rate-limit | 8/10 |
| **db/** | 1.002 | 8 | ORM SQLAlchemy async, 16 entidades, CRUD, refresh tokens | 8/10 |
| **domain/** | 385 | 5 | Value objects, entities, repositories (interfaces), exceptions | 8/10 |
| **infra/** | 162 | 4 | Implementações SQL dos repositórios | 7/10 |
| **matchers/** | 3.022 | 16 | Pipeline fiscal (forensics, regime, conformidade, enrich) | 8.5/10 |
| **parsers/** | 700 | 8 | Extração OFX/XML/PDF/CSV + anomalias | 8/10 |
| **routers/** | 2.567 | 15 | 49 endpoints HTTP REST | 7.5/10 |
| **services/** | 4.919 | 18 | Orquestração, render (laudo/excel/pdf), auth, LLM | 6.5/10 |
| **usecases/** | 131 | 4 | Use cases (clientes, conciliações) — clean arch parcial | 7/10 |

**Total Backend: ~14.049 LOC** (era 9.250 em 2026-05-28; +52%)

### 1.3 Pipeline Fiscal — o diferencial do produto

```
OFX + XMLs (NF-e/CT-e) → parsers/ → cascata.py (6 estágios) → orquestrador.py
   ↓
  Estágio 0 transf interna · 1 cadastro · 2 NF-e · 3 tarifa · 4 guia · 5 contrato · 6 fuzzy
   ↓
  ENRIQUECIMENTO: cnpj_enricher (RFB/BrasilAPI → situação/porte/pós-baixa)
   ↓
  forensics (smurfing, carrossel, valor redondo, risk_score 0-100)
   ↓
  auditoria_forense (regime×teto, heatmap, sinais) + conformidade (vol_nf/vol_pago)
   ↓
  services/laudo_forense.py → XLSX 11/13 abas + MD + HTML + PDF
```

**Endpoints fiscais** (`routers/fiscal.py`): `POST /fiscal/processar`, `POST /fiscal/laudo`, `POST /fiscal/laudo/resumo`, `GET /fiscal/{conformidade,gap,risco-tributario,documentos}/{id}`, `POST /fiscal/gerar-carta/{id}`, `GET /fiscal/cartas/{id}`.

### 1.4 Padrão Arquitetural

✅ **Clean Architecture em camadas** (routers → services → matchers/parsers → db → core), async/await consistente, Repository Pattern (domain+infra), Value Objects, Chain of Responsibility (cascata de 6 estágios).

⚠️ **Pontos de atenção:**
- **Fat file:** `services/laudo_forense.py` (1.909 LOC) concentra parse + cálculo + render (XLSX/MD/HTML/PDF). Candidato a extrair camada `calculations/`.
- **`services/` heterogêneo** (4.919 LOC): auth + excel + fiscal + LLM sem namespacing claro.
- **`matchers/orquestrador.py`** importa todos os estágios (acoplamento por design da cascata).
- Outros fat files: `routers/fiscal.py` (692), `services/excel.py` (574), `db/models.py` (401).

**Pontuação Backend: 8/10** — Maduro e bem testado; refatoração do laudo_forense pendente.

---

## 2. ARQUITETURA FRONTEND — React 19 + TypeScript

### 2.1 Visão Geral

```
React 19 + Router v7 (basename /app) + Context API + Tailwind + shadcn/ui
│
├─ Pages: 15 (14 protegidas + Login), todas lazy-loaded
├─ Components: ~38 (8 ui shadcn + 15 dashboard + 7 core + 8 skeletons)
├─ State: AuthProvider (JWT + refresh) · ThemeProvider (dark mode)
├─ API: lib/api.ts (761 LOC) — apiFetch<T> + apiFetchBlob + 50+ endpoints
└─ Styling: Tailwind + dark mode (CSS vars, localStorage)
```

### 2.2 Páginas por área (Sidebar)

| Área | Páginas |
|------|---------|
| **Operação (8)** | Dashboard · Conciliação · Upload · Matchers · Guias · Contratos · Clientes · Relatórios |
| **Fiscal (5)** | Conformidade · Gaps Fiscais · Risco Tributário · **Auditoria Forense** (nova) · Cartas |
| **Compliance (1)** | Configurações |
| **Auth (1)** | Login |

### 2.3 Componentes

| Categoria | Qtd | Exemplos |
|-----------|-----|----------|
| **ui/ (shadcn)** | 8 | button, dialog, input, label, select, sheet, skeleton, sonner |
| **dashboard/** | 15 | KpiCard, TrustGrid, SecurityRing, ActivityFeed, AuditTimeline, Heatmap, TrendChart |
| **core** | 7 | Sidebar, Topbar, ErrorBoundary, HeroCard, Logo, Starfield, PaletteStrip |
| **skeletons** | 8 | KpiGrid, Table, Page, AppBoot (com ARIA role=status) |

### 2.4 lib/ (936 LOC)

| Arquivo | LOC | Responsabilidade |
|---------|-----|------------------|
| **api.ts** | 761 | `apiFetch<T>` + `apiFetchBlob` (download autenticado) + 50+ endpoints + ~30 interfaces; token em sessionStorage, refresh-on-401 |
| auth.tsx | 73 | AuthProvider + useAuth (user/login/logout, evento global de logout) |
| theme.tsx | 38 | ThemeProvider + useTheme (light/dark, localStorage) |
| hooks.ts / utils.ts / constants.ts / recharts.ts | ~64 | useClock, cn/formatBytes, mapeamentos, config de charts |

### 2.5 Padrões

✅ Lazy loading (todas as páginas), ApiError + ErrorBoundary, skeletons por página, dark mode, a11y (axe-core, ARIA).
⚠️ **TypeScript não-strict** (`noUnusedLocals/Parameters: false`), 10/15 páginas sem teste, hooks customizados mínimos.

**Pontuação Frontend: 6.5/10** — Bem organizado; cobertura de testes de página ainda baixa.

---

## 3. TESTES & QUALIDADE

### 3.1 Backend (pytest)

| Métrica | Valor | Status |
|---------|-------|--------|
| **Total de testes** | **446** | ✅ Forte |
| **Cobertura** | 74% (`--cov-fail-under=74`, bloqueante) | ✅ Boa |
| **Arquivos** | 32 `test_*.py` | ✅ |
| **DB em testes** | Postgres NullPool (skip se sem DATABASE_URL) | ✅ Isolado |

Principais: `test_api.py` (68 KB), `test_coverage_boost.py`, `test_fiscal_cluster.py`, `test_matchers_*` (nfe/orquestrador/guia_contrato), `test_laudo_forense.py` + `test_laudo_resumo_endpoint.py` (novos), `test_prometheus_metrics.py`, `test_refresh_tokens.py`.

**Pontuação Backend Tests: 8.5/10**

### 3.2 Frontend (Vitest + Playwright)

| Métrica | Valor | Status |
|---------|-------|--------|
| **Testes de página** | 5/15 (Dashboard, Conciliacao, Clientes, Conformidade, Risco) | ⚠️ Melhorou (era 0) |
| **Componentes/lib** | ErrorBoundary, a11y, coreComponents, api, auth | ✅ |
| **E2E** | 4 specs (login, dashboard, clientes, errors) | ✅ Happy paths |

**Gap:** 10 páginas sem teste (inclui AuditoriaForensePage 528 LOC, CartasFiscais, Upload, Matchers).

**Pontuação Frontend Tests: 5.5/10**

### 3.3 Cobertura Geral

```
Backend (Python):  ███████░░  74%     ✅ Strong (gate no CI)
Frontend (React):  ███░░░░░░  ~25%    ⚠️  5 páginas + libs
E2E:               ████░░░░░  ~40%    ⚠️  Happy paths
```

**Pontuação Tests Geral: 7/10**

---

## 4. OBSERVABILIDADE & DEVOPS

### 4.1 Observabilidade

| Sistema | Status | Detalhes |
|---------|--------|----------|
| **Prometheus** | ✅ **NOVO** | `/metrics` — http_requests_total, request_duration, in_progress, llm_tokens, llm_cost_usd (`core/prometheus_metrics.py`) |
| **Sentry** | ✅ | `core/observability.py` — init opcional, PII masking (CPF/CNPJ/email/IP), traces 0.1 |
| **Logging** | ✅ | JSON estruturado, request_id, PII masking |
| **Rate limiting** | ✅ | SlowAPI 120/min, key por JWT sub → IP |
| **Health/Synthetic** | ✅ | `/health` + workflow synthetic-monitor (probe 30 min) |

**Pontuação Observabilidade: 8/10**

### 4.2 CI/CD (GitHub Actions)

| Job | Faz | Status |
|-----|-----|--------|
| **test** | pytest + cobertura 74% + weasyprint | ✅ |
| **security** | pip-audit, bandit, semgrep, Trivy, grep de chaves | ✅ |
| **frontend** | npm ci, build, tsc --noEmit, vitest, npm audit | ✅ |
| **e2e** | Playwright com backend :8765 | ✅ |
| **lint** | ruff **bloqueante** (black informativo) | ✅ Resolvido |
| **deploy** | Railway nativo (push main → build Docker → deploy) | ✅ Resolvido |

**Pontuação CI/CD: 8/10** — Só falta ambiente de staging.

### 4.3 Deploy / Runtime

- **Dockerfile multi-stage:** Node 22 builda o React → estágio Python 3.11 serve `dist` em `/app` (same-origin, `api/main.py:93`).
- **Railway** nativo (`railway.json`, healthcheck `/health`); GitHub Pages **removido** (era risco de vazamento).
- Postgres/Supabase; cache de CNPJ e datasets migrados para Postgres (compartilhado entre réplicas).

### 4.4 Documentação DevOps

| Doc | Cobre |
|-----|-------|
| README · DEPLOY · RUNBOOK · MONITORING · BACKUP · SCHEMA | dev setup, Railway, incidentes/rollback, Sentry/Prometheus/SLOs, backup, schema |

**Pontuação Documentação: 7.5/10** (era 5.0) **· DevOps Geral: 8/10**

---

## 5. PONTUAÇÃO GERAL

```
Backend:           8.0/10  ████████░
Frontend:          6.5/10  ██████░░░
Testing:           7.0/10  ███████░░
DevOps:            8.0/10  ████████░
Documentation:     7.5/10  ███████░░
Security:          7.5/10  ███████░░
Observability:     8.0/10  ████████░
Maintainability:   7.0/10  ███████░░
─────────────────────────────────────
📊 PONTUAÇÃO GERAL: 7.6/10  ████████░  (era 6.4)
```

**Interpretação:** ✅ MVP-ready · 🟢 Production-ready (deploy/observabilidade resolvidos) · 🟡 Enterprise-ready pendente (staging, cobertura frontend, refator de fat files).

---

## 6. TOP MELHORIAS PRIORITÁRIAS (atualizado)

### ✅ Resolvidas desde 2026-05-28
- Deploy frontend seguro (same-origin Railway, Pages removido)
- Railway automation (build Docker + deploy no push main)
- Prometheus `/metrics` implementado
- Lint ruff bloqueante no CI
- 5 páginas frontend agora testadas (eram 0)

### 🔴 P0 — Crítica (0-2 semanas)
1. **Ambiente de staging** — único P0/P1 antigo ainda pendente; deploy vai direto main→prod. Mitigado por CI + healthcheck + Sentry, mas sem validação de migrations pré-prod.
2. **Lint `react-hooks/set-state-in-effect`** — erro pré-existente em páginas (padrão de fetch em `useEffect`); destrava o `npm run lint` do frontend.

### 🟠 P1 — Alta (2-4 semanas)
3. **Cobertura de testes nas 10 páginas restantes** — prioridade AuditoriaForensePage (528 LOC), Upload, Matchers.
4. **Refatorar `services/laudo_forense.py` (1.909 LOC)** — extrair camada de cálculo (agregação/heatmap) de render.
5. **Namespacing de `services/`** — agrupar `fiscal_*`, `conciliacao_*`, `ai_*`.

### 🟡 P2 — Média (1-2 meses)
6. **TypeScript strict** no frontend (`noUnusedLocals/Parameters`).
7. **Multi-instância plena** — migrar rate-limiter e acumulador de custo LLM (in-memory) para Redis/Postgres (datasets e cnpj_cache já migrados).
8. **Storybook / design-system docs** para os componentes.

---

## 7. CONCLUSÕES

### ✅ Pontos Fortes
1. **Pipeline fiscal forense** sólido e diferenciado (cascata 6 estágios, regime×teto, forensics, enriquecimento RFB) — reproduz laudo real ao centavo.
2. **Backend maduro** — 446 testes, 74% cobertura bloqueante, clean architecture.
3. **DevOps resolvido** — deploy seguro same-origin, Railway automático, Prometheus + Sentry, synthetic monitor.
4. **Persistência compartilhada** — datasets e cnpj_cache em Postgres (multi-réplica viável).
5. **Documentação DevOps** completa (RUNBOOK, MONITORING, DEPLOY, BACKUP).

### ⚠️ Pontos Fracos
1. **Cobertura frontend** — 10/15 páginas sem teste; TS não-strict.
2. **Sem staging** — migrations validadas só em prod.
3. **Fat files** — laudo_forense.py (1.909), services heterogêneo.
4. **Multi-instância parcial** — rate-limiter e custo LLM ainda in-memory.

### 🎯 Recomendação
**Status:** Production-ready. Próximos passos: staging + cobertura de páginas + refator do laudo_forense. Nota projetada pós-P0/P1: ~8.5/10.

---

## 8. ANEXO — Estrutura de Diretórios

```
OrgConc/
├─ api/                         (FastAPI, ~14.049 LOC)
│  ├─ core/        (986)  config, prometheus, observability, llm_metrics, rate_limit
│  ├─ db/          (1.002) models (16 entid.), metrics, refresh_tokens, CRUD
│  ├─ domain/      (385)  value objects, entities, repositories, exceptions
│  ├─ infra/       (162)  repositórios SQL
│  ├─ matchers/    (3.022) forensics, cnpj_enricher, orquestrador, auditoria_forense, cascata...
│  ├─ parsers/     (700)  ofx, xml, pdf, csv, anomalies, classifier
│  ├─ routers/     (2.567) 15 routers, 49 endpoints
│  ├─ services/    (4.919) laudo_forense (1.909), excel, carta, conciliacao_llm, auth, ai...
│  ├─ usecases/    (131)  clientes, conciliações
│  ├─ main.py · schemas.py
├─ orgconc-react/               (React 19 + Vite, ~9.000 LOC src)
│  ├─ src/pages/    (15 páginas + 5 testes)
│  ├─ src/components/ (ui 8 · dashboard 15 · core 7 · skeletons 8)
│  ├─ src/lib/      (api.ts 761, auth, theme, hooks, utils)
│  └─ e2e/          (4 specs Playwright)
├─ tests/                       (446 testes, 32 arquivos)
├─ migrations/versions/         (12 migrations Alembic; última: 012_cnpj_cache)
├─ scripts/                     (21 scripts; relatorio_integrado.py = CLI do laudo)
├─ docs/ + README · DEPLOY · RUNBOOK · MONITORING · BACKUP · SCHEMA
├─ Dockerfile (multi-stage) · docker-compose.yml · railway.json
└─ .github/workflows/ (ci.yml: test/security/frontend/e2e · synthetic-monitor.yml)
```

---

**Gerado:** 2026-06-02 · **Remapeamento automático** (3 agentes: backend, frontend, infra) + métricas `git ls-files`/`pytest --collect-only`.
**Próxima revisão:** após staging + cobertura de páginas.
