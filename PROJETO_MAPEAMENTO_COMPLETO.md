# OrgConc — Mapeamento Completo de Módulos & Relatório de Pontuação

**Data:** 2026-06-09 · **números revisados em 2026-06-11** (pós PRs #106–#110 e hardening Fable)
**Projeto:** OrgConc (Conciliação Bancária + Auditoria Fiscal Forense — FastAPI + React + Supabase/Postgres)
**Versão:** 0.5.0 — beta avançado **em produção** (Railway + Supabase, RLS real por `org_id`)
**Branch:** `claude/optimistic-hermann-ffd614`
**Remapeamento anterior:** 2026-06-02 (7.6/10) · antes: 2026-05-28 (6.4/10)
**Complementa:** `docs/ESTADO_PROJETO_2026-06-11.md` (status do hardening de segurança)

---

## SUMÁRIO EXECUTIVO

| Métrica | Valor | Status |
|---------|-------|--------|
| **Backend (Python)** | ~15.988 LOC · 9 subpacotes | ✅ Clean Architecture em camadas |
| **Frontend (React/TS)** | ~9.164 LOC src · 17 páginas | ✅ React 19 + Tailwind 4 + shadcn/ui |
| **Endpoints HTTP** | 56 rotas em 16 routers | ✅ REST + auth JWT multi-org |
| **Matchers (domínio fiscal)** | 3.205 LOC · 16 arquivos | ✅ Diferencial do produto |
| **Multi-tenancy** | RLS real por `org_id`, FORCE RLS, fail-closed | ✅ **Enforçado em prod** |
| **Testes Backend** | **715 funções** · 46 arquivos · **gate 80%** no CI (#110) | ✅ Forte |
| **Testes Frontend** | **347 testes** · 17/17 páginas + componentes · cobertura ~88% (gate 84/76/83/86, #109) · 4 E2E | ✅ Gate ativo (2026-06-09) |
| **Observabilidade** | Prometheus `/metrics` + Sentry + log JSON | ✅ Implementado |
| **Deploy** | Railway (Docker multi-stage, React same-origin `/app`) | ✅ Seguro e automático |
| **CI/CD** | test · security · frontend · e2e + synthetic monitor | ✅ Lint ruff bloqueante |
| **Migrations** | 20 (cadeia linear 001→020, head `020_org_id_fiscais`) | ✅ Sem fork |
| **Pontuação Geral** | **7.8 / 10** | 🟢 Production-ready multi-tenant (falta staging) |

> **Evolução vs 2026-06-02:** +14% LOC backend (14.049→15.988), +7 endpoints, +8 migrations (12→20),
> +72 testes (446→518). O salto qualitativo foi **multi-tenancy de produção** (RLS real por `org_id`,
> enforçado e re-auditado live), login ORGATEC, admin de usuários/orgs, e migração de stack
> (Tailwind 4, bcrypt 5). Nota geral 7.6 → **7.8**.

---

## 0. O QUE MUDOU DESDE 2026-06-02 (PRs #61–#101)

| Eixo | Entregas | PRs |
|------|----------|-----|
| **Multi-tenancy / RLS** | `org_id` nas fiscais, usuários multi-org, login por usuário+org no token, RLS Fase A → enforcement, `app_orgconc` NOBYPASSRLS, superadmin cross-org read-only, `ALEMBIC_DATABASE_URL` (owner) separado do runtime | #73–#84 |
| **Admin** | Página de gestão de usuários e organizações (`UsuariosPage` 368 LOC) | #85 |
| **Dashboard** | Redesign Fases 0–2: trust score honesto no vazio, empty-first, bento, a11y, command palette ⌘K, Insights IA desacoplados, cache por tenant (fix cross-tenant) | #87–#94 |
| **Auth/UI** | Nova tela de login na identidade ORGATEC; troca/reset de senha (revoga refresh tokens) | #77, #95 |
| **Deps (majors)** | GH Actions bump; **bcrypt 5** (passlib removido); **Tailwind 4** (CSS-first `@theme`, sem `tailwind.config.js`) | #96–#100 |
| **CBS/IBS** | Scaffold + Fase 1 (mapeamento regime-geral) + pre-flight de versão da base | #70–#72 |
| **Resiliência** | Rate-limit Redis-ready (`REDIS_URL` opcional); PDF via **WeasyPrint** (Playwright proibido) | #66–#68 |
| **Privacidade** | Remoção de dados/caminhos LOCAR hardcoded e scripts one-off | #61–#62 |
| **Docs** | Roadmap 1.0 priorizado; runbook de migração fiscal; doc do laudo forense | #101 |

---

## 1. ARQUITETURA BACKEND — Análise Estrutural

### 1.1 Visão Geral (camadas)

```
┌──────────────────────────────────────────────────────────────┐
│ HTTP: routers/ (16 arquivos, 56 endpoints, 3.018 LOC)         │
│ ├─ fiscal.py (799) · conciliacao.py (462) · auth_routes (460) │
│ └─ metrics · guias · contratos · matchers · clientes · audit  │
│    · activity · transacoes · ai · conciliacoes_list · exports │
└───────────────────────────────┬──────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────┐
│ Application: services/ (20 arq, 5.648 LOC)                    │
│ ├─ laudo_forense.py (2.103 ⚠) · excel.py (574)               │
│ ├─ fiscal_persistence · carta_constatacao · calculadora_cbs  │
│ ├─ auth · conciliacao_llm · ai_insights · report_utils       │
│ └─ fiscal_notifications · fiscal_job · sefaz_distribuicao ... │
└───────┬──────────────────────────────────────────────┬───────┘
        ↓                                                ↓
┌────────────────────────────┐              ┌───────────────────┐
│ Domínio: matchers/ (3.205)  │              │ parsers/ (700)    │
│ ├─ cnpj_enricher (476)      │              │ ├─ anomalies      │
│ ├─ forensics (411)          │              │ ├─ pdf · ofx      │
│ ├─ xml_fiscal (391)         │              │ └─ xml · csv      │
│ └─ orquestrador (260) · ... │              └───────────────────┘
└──────────────┬──────────────┴───────────────────────┬─────────┘
               ↓                                        ↓
     ┌──────────────────────┐              ┌────────────────────────┐
     │ domain/ (385) + infra │              │ db/ (1.311 LOC)        │
     │ value objects, repos  │              │ models.py (19 entid.)  │
     └──────────────────────┘              │ metrics · audit · RLS  │
                                           └────────────┬───────────┘
                                                        ↓
                              ┌──────────────────────────────────────┐
                              │ core/ (1.093): config · prometheus    │
                              │ observability · llm_metrics · ratelim │
                              └──────────────────────────────────────┘
```

### 1.2 Módulos Principais

| Módulo | LOC | Arq. | Responsabilidade | Pontuação |
|--------|-----|------|------------------|-----------|
| **core/** | 1.093 | 10 | Config, Prometheus, observability (Sentry), llm_metrics, rate-limit (Redis-ready) | 8/10 |
| **db/** | 1.311 | 10 | ORM SQLAlchemy async, 19 entidades, CRUD, refresh tokens, contexto RLS | 8/10 |
| **domain/** | 385 | 5 | Value objects, entities, repositories (interfaces), exceptions | 8/10 |
| **infra/** | 162 | 4 | Implementações SQL dos repositórios | 7/10 |
| **matchers/** | 3.205 | 16 | Pipeline fiscal (forensics, regime, conformidade, enrich, xml_fiscal) | 8.5/10 |
| **parsers/** | 700 | 8 | Extração OFX/XML/PDF/CSV + anomalias | 8/10 |
| **routers/** | 3.018 | 16 | 56 endpoints HTTP REST | 7.5/10 |
| **services/** | 5.648 | 20 | Orquestração, render (laudo/excel/pdf), auth, LLM, CBS/IBS | 6.5/10 |
| **usecases/** | 131 | 4 | Use cases (clientes, conciliações) — clean arch parcial | 7/10 |

**Total Backend: ~15.988 LOC** (era 14.049 em 2026-06-02; +14%)

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
  services/laudo_forense.py → XLSX 11/13 abas + MD + HTML + PDF (WeasyPrint)
```

**CBS/IBS (camada IC-02):** OrgConc **orquestra** a calculadora oficial (não recalcula).
`services/calculadora_cbs_ibs.py` + transporte genérico (`CALCULADORA_BASE_URL`).
Persistência em `apuracao_cbs_ibs` (migrations 013/014/018). ✅ **SERPRO removido** no PR #106
(2026-06-09): `serpro_client.py` deletado, OAuth2/Consumer-Key fora; alvo é a API do portal
Tributos (`consumo.tributos.gov.br`).

**Endpoints fiscais** (`routers/fiscal.py`, 799 LOC): `POST /fiscal/processar`, `POST /fiscal/laudo`,
`POST /fiscal/laudo/resumo`, `POST /fiscal/apurar` (CBS/IBS), `GET /fiscal/{conformidade,gap,
risco-tributario,documentos}/{id}`, `POST /fiscal/gerar-carta/{id}`, `GET /fiscal/cartas/{id}`.

### 1.4 Padrão Arquitetural

✅ **Clean Architecture em camadas** (routers → services → matchers/parsers → db → core), async/await
consistente, Repository Pattern (domain+infra), Value Objects, Chain of Responsibility (cascata de 6
estágios), **multi-tenancy por RLS** (contexto `org_id` injetado por request).

⚠️ **Pontos de atenção:**
- **Fat file:** `services/laudo_forense.py` (2.103 LOC, +194 desde 06-02) concentra parse + cálculo +
  render (XLSX/MD/HTML/PDF). Candidato a extrair camada `calculations/`.
- **`services/` heterogêneo** (5.648 LOC, 20 arq): auth + excel + fiscal + LLM + CBS/IBS sem
  namespacing claro.
- ~~Dívida SERPRO~~ — **removida no PR #106** (client deletado, transporte genérico).
- Outros fat files: `routers/fiscal.py` (799), `services/excel.py` (574), `db/models.py` (490).

**Pontuação Backend: 8/10** — Maduro, multi-tenant e bem testado; refator do laudo_forense + remoção
SERPRO pendentes.

---

## 2. ARQUITETURA FRONTEND — React 19 + TypeScript + Tailwind 4

### 2.1 Visão Geral

```
React 19 + Router v7 (basename /app) + Context API + Tailwind 4 (CSS-first) + shadcn/ui
│
├─ Pages: 17 (16 protegidas + Login), lazy-loaded
├─ Components: dashboard 12 · ui (shadcn) 9 · core 8
├─ State: AuthProvider (JWT + refresh + org) · ThemeProvider (dark mode)
├─ API: lib/api.ts (912 LOC) — apiFetch<T> + apiFetchBlob + 50+ endpoints
└─ Styling: Tailwind 4 (@theme em index.css, sem tailwind.config.js) + dark mode
```

### 2.2 Páginas por área (Sidebar)

| Área | Páginas |
|------|---------|
| **Operação (8)** | Dashboard · Conciliação · Upload · Matchers · Guias · Contratos · Clientes · Relatórios |
| **Fiscal (6)** | Conformidade · Gaps Fiscais · Risco Tributário · Auditoria Forense · Cartas · **Laudo** |
| **Admin (1)** | **Usuários** (gestão de usuários/orgs — nova) |
| **Compliance (1)** | Configurações |
| **Auth (1)** | Login (identidade ORGATEC — nova) |

### 2.3 lib/ (1.076 LOC)

| Arquivo | LOC | Responsabilidade |
|---------|-----|------------------|
| **api.ts** | 912 | `apiFetch<T>` + `apiFetchBlob` (download autenticado) + 50+ endpoints; token em sessionStorage, refresh-on-401 |
| auth.tsx | 74 | AuthProvider + useAuth (user/org/login/logout) |
| theme.tsx | 39 | ThemeProvider + useTheme (light/dark, localStorage) |
| constants · utils · hooks · risco-cores · recharts | ~86 | mapeamentos, cn/formatBytes, useClock, cores de risco, config charts |

### 2.4 Padrões

✅ Lazy loading, ApiError + ErrorBoundary, skeletons por página, dark mode, a11y (axe-core, ARIA,
command palette ⌘K), empty-first honesto, Tailwind 4, **TypeScript `strict: true`** (ativado 2026-06-11; antes só `noUnusedLocals/Parameters`), `tsc --noEmit` bloqueante no CI.
✅ **17/17 páginas com teste** + gate de cobertura (2026-06-09).

**Pontuação Frontend: 7.5/10** — UX/a11y maduras, TS strict, cobertura com gate.

---

## 3. TESTES & QUALIDADE

### 3.1 Backend (pytest)

| Métrica | Valor | Status |
|---------|-------|--------|
| **Funções de teste** | **715** | ✅ Forte |
| **Cobertura** | 80% (`--cov-fail-under=80`, bloqueante no CI — #110) | ✅ Boa |
| **Arquivos** | 46 `test_*.py` | ✅ |
| **DB em testes** | Postgres NullPool (skip se sem DATABASE_URL) | ✅ Isolado |

### 3.2 Frontend (Vitest + Playwright)

| Métrica | Valor | Status |
|---------|-------|--------|
| **Total de testes** | **347** (era ~40) | ✅ |
| **Páginas testadas** | **17/17** | ✅ Cobertas (2026-06-09) |
| **Cobertura** | stmts 86% · lines 88.6% · funcs 85.6% · branches 79.3% (`api.ts` 94%) | ✅ Gate no CI |
| **Gate** | `coverage.thresholds` (stmts 84/branches 76/funcs 83/lines 86); CI roda `test:coverage` | ✅ Bloqueante |
| **Componentes/lib** | ErrorBoundary, a11y, coreComponents, CommandPalette, AIInsightsPanel, AuditEventModal, api, auth | ✅ |
| **E2E** | 4 specs (login, dashboard, clientes, errors) | ✅ Happy paths |

**Resíduo p/ 80% (critério 1.0):** 4 páginas com testes rasos pré-existentes (Clientes 33%, Conciliacao 35%,
Conformidade 35%, Risco 45%) e AuditTimeline (31%) — aprofundar.

### 3.3 Cobertura Geral

```
Backend (Python):  ████████░  80%       ✅ Strong (gate no CI)
Frontend (React):  █████████  ~88%      ✅ Gate no CI (era ~25%)
E2E:               ████░░░░░  ~40%      ⚠️  Happy paths (P0 #5: aprofundar)
```

**Pontuação Tests Geral: 7.5/10** (era 7.0 — gate frontend ativo)

---

## 4. OBSERVABILIDADE & DEVOPS

### 4.1 Observabilidade

| Sistema | Status | Detalhes |
|---------|--------|----------|
| **Prometheus** | ✅ | `/metrics` — http_requests_total, request_duration, in_progress, llm_tokens, llm_cost_usd |
| **Sentry** | ✅ | `core/observability.py` — init opcional, PII masking (CPF/CNPJ/email/IP), traces 0.1 |
| **Logging** | ✅ | JSON estruturado, request_id, PII masking |
| **Rate limiting** | ✅ | SlowAPI 120/min, key por JWT sub → IP; **Redis-ready** (`REDIS_URL` opcional) |
| **Health/Synthetic** | ✅ | `/health` + workflow synthetic-monitor (probe 30 min) |

**Pontuação Observabilidade: 8/10**

### 4.2 CI/CD (GitHub Actions)

| Job | Faz | Status |
|-----|-----|--------|
| **test** | pytest + cobertura 80% + weasyprint | ✅ |
| **security** | pip-audit, bandit, semgrep, Trivy, grep de chaves | ✅ |
| **frontend** | npm ci, build, tsc --noEmit, vitest, npm audit | ✅ |
| **e2e** | Playwright com backend :8765 | ✅ |
| **lint** | ruff **bloqueante** (black informativo) | ✅ |
| **deploy** | Railway nativo (push main → build Docker → `preDeployCommand` alembic → deploy) | ✅ |

**Migrations em deploy:** `railway.json` roda `alembic upgrade head` em `preDeployCommand`, com
`ALEMBIC_DATABASE_URL` (owner) separado do runtime `app_orgconc` (NOBYPASSRLS).

**Pontuação CI/CD: 8/10** — Só falta ambiente de staging.

### 4.3 Deploy / Runtime

- **Dockerfile multi-stage:** Node 22 builda o React → estágio Python 3.12 serve `dist` em `/app`
  (same-origin, `api/main.py:94`).
- **Railway** nativo (`railway.json`, healthcheck `/health`); GitHub Pages **removido**.
- Postgres/Supabase; cache de CNPJ e datasets em Postgres (compartilhado entre réplicas).
- ⚠️ **Drift de comentário:** `api/main.py:90-91` ainda cita "GitHub Pages (ver deploy.yml)" —
  desatualizado (Pages removido); corrigir.

### 4.4 Documentação

| Doc | Cobre |
|-----|-------|
| README · DEPLOY · RUNBOOK · MONITORING · BACKUP · SCHEMA | dev setup, Railway, incidentes, SLOs, backup, schema |
| docs/ROADMAP_1.0 · FISCAL_MIGRATION_RUNBOOK · LAUDO_FORENSE · PLANEJAMENTO_DASHBOARD_TRUST | roadmap, migração fiscal, laudo, dashboard |

⚠️ **README desatualizado:** cita `static/` (UI legada em `/ui/`) que **não existe mais**; não menciona
fiscal/laudo/RLS/multi-tenancy. **Corrigido neste ciclo.**

**Pontuação Documentação: 7.5/10**

---

## 5. PONTUAÇÃO GERAL

```
Backend:           8.0/10  ████████░
Frontend:          7.0/10  ███████░░
Testing:           7.0/10  ███████░░
DevOps:            8.0/10  ████████░
Documentation:     7.5/10  ███████░░
Security:          8.5/10  ████████▌   ↑ (RLS real enforçado + bcrypt 5 + reset c/ revogação)
Observability:     8.0/10  ████████░
Maintainability:   7.0/10  ███████░░
─────────────────────────────────────
📊 PONTUAÇÃO GERAL: 7.8/10  ████████░  (era 7.6)
```

**Interpretação:** ✅ MVP-ready · 🟢 Production-ready **multi-tenant** (RLS real enforçado, fail-closed) ·
🟡 Enterprise-ready pendente (staging, cobertura frontend, refator de fat files, dívida SERPRO).

---

## 6. ACHADOS DESTE REMAPEAMENTO (drift & dívidas)

| # | Achado | Severidade | Ação |
|---|--------|------------|------|
| A1 | ~~SERPRO ainda no código~~ | 🟢 Resolvido | ✅ Removido no PR #106 (2026-06-09) |
| A2 | **README desatualizado** (cita `static/`/`/ui/` inexistente; sem fiscal/RLS) | 🟡 Baixa | ✅ Corrigido neste ciclo |
| A3 | ~~Comentário `main.py` cita GitHub Pages~~ | 🟢 Resolvido | ✅ Comentário atualizado |
| A4 | **Cobertura frontend** 5/17 páginas (proporção piorou com +2 páginas) | 🟠 Média | ✅ Resolvido (17/17 páginas, ~88%, gate 84/86 no CI — 2026-06-09) |
| A5 | **3 policies RLS legadas** `*_org_policy` inertes a limpar | 🟡 Baixa | Roadmap P0 #4 |
| A6 | **Fat file** `laudo_forense.py` cresceu (2.103 LOC) | 🟡 Baixa | Roadmap P1 (refator) |
| A7 | ~~Logout não revoga refresh token~~ — **claim incorreto:** `auth_logout` já revoga (`revogar_por_hash`); só o access JWT sobrevive até o TTL | 🟢 Resolvido | Verificado 2026-06-09 (+ testes logout-all; docstring do modelo de revogação) |

---

## 7. CONCLUSÕES

### ✅ Pontos Fortes
1. **Multi-tenancy de produção** — RLS real por `org_id`, FORCE RLS, fail-closed, re-auditado live;
   `app_orgconc` NOBYPASSRLS + owner separado para migrations.
2. **Pipeline fiscal forense** sólido e diferenciado (cascata 6 estágios, regime×teto, forensics,
   enriquecimento RFB) — reproduz laudo real ao centavo.
3. **Backend maduro** — 715 testes, 80% cobertura bloqueante, clean architecture.
4. **DevOps resolvido** — deploy seguro same-origin, Railway automático, Prometheus + Sentry, migrations
   em preDeploy com URL de owner separada.
5. **Segurança em alta** — bcrypt 5 (sem passlib), reset/troca de senha com revogação de refresh,
   superadmin cross-org read-only por policy.

### ⚠️ Pontos Fracos
1. **Sem staging** — migrations validadas só em prod (mitigado por preDeploy + healthcheck + Sentry).
2. **Fat files** — laudo_forense.py (2.103), services heterogêneo (5.648).
3. ~~Dívida SERPRO~~ — removida (PR #106).
4. **E2E raso** — happy paths; faltam fluxos de upload→resultado e auditoria forense.
5. **CBS/IBS sem idempotência** — `salvar_apuracao` insere sempre; falta UNIQUE/UPSERT.

> Resolvidos neste ciclo: cobertura frontend (17/17 + gate), TS strict (já estava),
> revogação de refresh no logout (já funcional + testes), headers de rate-limit no 429.

### 🎯 Recomendação
**Status:** Production-ready multi-tenant. Próximos passos por ordem de valor/risco: endurecimento P0
(cobertura frontend + gate, revogação no logout, rate-limit testado, limpeza RLS, E2E profundo) →
fiscal P1 (remover SERPRO, persistir apuração, catálogo de anomalias) → governança P2 (staging,
CHANGELOG, versionamento de API). Nota projetada pós-P0/P1: **~8.5/10**.

---

## 8. ANEXO — Estrutura de Diretórios

```
OrgConc/
├─ api/                         (FastAPI, ~15.988 LOC)
│  ├─ core/        (1.093) config, prometheus, observability, llm_metrics, rate_limit
│  ├─ db/          (1.311) models (19 entid.), metrics, refresh_tokens, contexto RLS
│  ├─ domain/      (385)  value objects, entities, repositories, exceptions
│  ├─ infra/       (162)  repositórios SQL
│  ├─ matchers/    (3.205) forensics, cnpj_enricher, xml_fiscal, orquestrador, cascata...
│  ├─ parsers/     (700)  ofx, xml, pdf, csv, anomalies, classifier
│  ├─ routers/     (3.018) 16 routers, 56 endpoints
│  ├─ services/    (5.648) laudo_forense (2.103), excel, fiscal_persistence, calculadora_cbs_ibs...
│  ├─ usecases/    (131)  clientes, conciliações
│  ├─ main.py · schemas.py · schemas_cbs_ibs.py
├─ orgconc-react/               (React 19 + Vite + Tailwind 4, ~9.164 LOC src)
│  ├─ src/pages/    (17 páginas + 5 testes de página)
│  ├─ src/components/ (dashboard 12 · ui 9 · core 8 · __tests__)
│  ├─ src/lib/      (api.ts 912, auth, theme, hooks, utils, risco-cores)
│  └─ e2e/          (4 specs Playwright)
├─ tests/                       (715 funções, 46 arquivos)
├─ migrations/versions/         (20 migrations Alembic; head: 020_org_id_fiscais)
├─ scripts/                     (CLI relatorio_integrado.py = laudo)
├─ db/rls/ · supabase/migrations/   (políticas RLS, org_isolation)
├─ docs/ + README · DEPLOY · RUNBOOK · MONITORING · BACKUP · SCHEMA
├─ Dockerfile (multi-stage) · docker-compose.yml · railway.json
└─ .github/workflows/ (ci.yml: test/security/frontend/e2e · synthetic-monitor.yml)
```

---

**Gerado:** 2026-06-09 · Métricas via `git ls-files`/`wc`/`grep` no estado atual do worktree.
**Próxima revisão:** após P0 (cobertura frontend + gate) e início do P1 fiscal (remoção SERPRO).
