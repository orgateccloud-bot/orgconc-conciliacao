# OrgConc — Dashboard de Pontuação & Prioridades

> 📜 **DOCUMENTO HISTÓRICO (arquivado em 2026-06-11).** Snapshot do baseline
> 6.4/10 de 2026-05-28. Dos 5 problemas P0 listados, 4 foram resolvidos até
> 2026-06-09 (deploy Railway same-origin, 17/17 páginas testadas com gate
> 84/86, DEPLOY/RUNBOOK/BACKUP escritos, `_legacy/` removido); os quick-wins
> TS strict e pre-commit entraram em 2026-06-11. Para o estado atual, ver
> `PONTUACAO_VISUAL.md` (raiz, dashboard vigente), `docs/ESTADO_PROJETO_2026-06-11.md`
> e `PROJETO_MAPEAMENTO_COMPLETO.md`.

**Atualizado:** 2026-05-28

---

## 📊 SCORECARD GERAL

```
BACKEND ARCHITECTURE          7.5/10  ████████░░░░░░░░░░░  (Excelente)
FRONTEND ARCHITECTURE         5.5/10  ██████░░░░░░░░░░░░░░  (Regular)
TESTING & COVERAGE            6.0/10  ██████░░░░░░░░░░░░░░  (Inadequado)
DEVOPS & DEPLOYMENT           5.5/10  ██████░░░░░░░░░░░░░░  (Gaps críticos)
DOCUMENTATION                 5.0/10  █████░░░░░░░░░░░░░░░  (Gaps significativos)
SECURITY                      7.0/10  ███████░░░░░░░░░░░░░  (Bom)
PERFORMANCE                   7.0/10  ███████░░░░░░░░░░░░░  (Bom)
MAINTAINABILITY               7.0/10  ███████░░░░░░░░░░░░░  (Bom)
════════════════════════════════════════════════════════════
🎯 OVERALL SCORE              6.4/10  ██████░░░░░░░░░░░░░░░  (MVP-Ready)
```

---

## 🔍 DETALHES POR MÓDULO

### Backend (Python)

```
core/          [████████░] 8/10  Infraestrutura sólida
db/            [████████░] 8/10  ORM bem estruturado
matchers/      [████████░] 8/10  Lógica fiscal robusta
parsers/       [████████░] 8/10  Parsing bem testado
routers/       [███████░░] 7/10  Acoplamento moderado
services/      [██████░░░] 6/10  Coesão baixa, refatorar
schemas/       [████████░] 8/10  Validação clara
main.py        [████████░] 8/10  Inicialização OK
```

### Frontend (React)

```
Pages          [███░░░░░░] 3/10  SEM TESTES ❌
Components     [████░░░░░] 4/10  Minimamente testados
Dashboard      [████░░░░░] 4/10  Sem testes unitários
Core/Layout    [███████░░] 7/10  Testado (ErrorBoundary)
Hooks/Lib      [███████░░] 7/10  API bem testada
E2E            [██████░░░] 6/10  Fluxos críticos cobertos
```

### Testes (Cobertura Real)

```
Backend Unit       [████████░] 75-85%  ✅ Excelente
Frontend Unit      [██░░░░░░░]  2-5%   ❌ Crítico
Frontend E2E       [██████░░░] 40-50%  ⚠️  Parcial
Backend Coverage   [████████░]   85%   ✅ Ótima
Frontend Coverage  [██░░░░░░░]   2%    ❌ Inadequada
Overall Coverage   [██████░░░]  50%    🟡 Desigual
```

### DevOps

```
CI/CD Tests        [███████░░] 7/10   ✅ Funcional
CI/CD Deploy       [███░░░░░░] 3/10   ❌ Incompleto
Observability      [███████░░] 7/10   ✅ Sentry + Logging
Deployment Docs    [░░░░░░░░░] 0/10   ❌ Não existe
Railway Config     [████░░░░░] 4/10   ⚠️  Pronto mas não automatizado
Staging Env        [░░░░░░░░░] 0/10   ❌ Não existe
Disaster Recovery  [░░░░░░░░░] 0/10   ❌ Nenhum runbook
```

---

## 🚨 PROBLEMAS CRÍTICOS (P0)

| # | Problema | Severidade | Impacto | Prazo |
|---|----------|-----------|---------|-------|
| 1 | **Frontend deploy expõe código backend** | 🔴 CRÍTICA | Vazamento de segurança | HOJE |
| 2 | **Deploy em produção não automatizado** | 🔴 CRÍTICA | Impossível deploar | 1 sem |
| 3 | **Zero testes em 14 páginas** | 🔴 CRÍTICA | Regressões invisíveis | 2-3 sem |
| 4 | **Sem staging environment** | 🔴 CRÍTICA | Risco de quebrar produção | 1 sem |
| 5 | **Services module: coesão muito baixa** | 🟠 ALTA | Difícil manutenção | 2 sem |

---

## 📋 TOP 10 AÇÕES

### Semana 1 — CRÍTICO (Unblock Deployment)

```
┌─────────────────────────────────────────────────────┐
│ ✓ TASK 1: Fix GitHub Pages frontend deploy        │
│   └─ Modificar deploy.yml para upload apenas dist/│
│      Tempo: 15 min | Criticidade: 🔴 MÁXIMA       │
├─────────────────────────────────────────────────────┤
│ ✓ TASK 2: Staging environment setup               │
│   └─ Railway staging app + copiar secrets         │
│      Tempo: 1 dia | Criticidade: 🔴 MÁXIMA        │
├─────────────────────────────────────────────────────┤
│ ✓ TASK 3: Deploy automation (Railway)             │
│   └─ GitHub Actions job: test → deploy → healthcheck
│      Tempo: 1 dia | Criticidade: 🔴 MÁXIMA        │
├─────────────────────────────────────────────────────┤
│ ✓ TASK 4: Deployment guide (doc)                  │
│   └─ Railway secrets, env vars, health check      │
│      Tempo: 2h | Criticidade: 🟠 ALTA             │
└─────────────────────────────────────────────────────┘
```

### Semana 2-3 — FRONTEND TESTS

```
┌─────────────────────────────────────────────────────┐
│ ✓ TASK 5: Page tests (5 critical pages)            │
│   └─ DashboardPage, ConciliacaoPage, ClientesPage │
│      ├─ Testam renders, API calls, error states   │
│      └─ Tempo: 3 dias | Criticidade: 🔴 ALTA      │
├─────────────────────────────────────────────────────┤
│ ✓ TASK 6: Component tests (core widgets)          │
│   └─ Sidebar, Topbar, KpiCard, ActivityFeed, etc  │
│      └─ Tempo: 2 dias | Criticidade: 🟠 ALTA      │
├─────────────────────────────────────────────────────┤
│ ✓ TASK 7: Runbooks (3 docs)                        │
│   └─ Troubleshooting, Disaster Recovery, Rollback │
│      └─ Tempo: 2 dias | Criticidade: 🟠 ALTA      │
└─────────────────────────────────────────────────────┘
```

### Semana 4+ — REFACTORING

```
┌─────────────────────────────────────────────────────┐
│ ✓ TASK 8: Clean up legacy code                     │
│   └─ Remover /components/_legacy/ (4 componentes) │
│      └─ Tempo: 1 dia | Criticidade: 🟡 MÉDIA      │
├─────────────────────────────────────────────────────┤
│ ✓ TASK 9: Services refactoring                     │
│   └─ Quebrar em: auth/, export/, fiscal/, llm/    │
│      └─ Tempo: 2 dias | Criticidade: 🟡 MÉDIA     │
├─────────────────────────────────────────────────────┤
│ ✓ TASK 10: Prometheus metrics                      │
│   └─ /metrics endpoint + alerting setup           │
│      └─ Tempo: 2 dias | Criticidade: 🟡 MÉDIA     │
└─────────────────────────────────────────────────────┘
```

---

## 📈 TIMELINE DE MELHORIA

```
AGORA                  SEMANA 1          SEMANA 2-4       MÊS 2
├─────────┬────────────┼──────────────────┼────────────────┼──────────────
│ Baseline│ Deploy Fix │ Frontend Tests   │ Refactoring    │ Production
│ 6.4/10  │ 6.8/10     │ 7.5/10          │ 8.2/10        │ 8.5+/10
│         │            │                  │                │
│ 📊Stats │ 📊Stats    │ 📊Stats         │ 📊Stats       │ 📊Stats
│ Backend:7.5    │ Backend:7.5 │ Backend:7.5     │ Backend:8.0    │ Backend:8.0
│ Frontend:5.5   │ Frontend:5.5│ Frontend:7.0    │ Frontend:7.5   │ Frontend:8.0
│ DevOps:5.5     │ DevOps:7.0  │ DevOps:7.5      │ DevOps:8.0     │ DevOps:8.5
│ Tests:6.0      │ Tests:6.2   │ Tests:8.0       │ Tests:8.5      │ Tests:9.0
│ Docs:5.0       │ Docs:6.0    │ Docs:7.0        │ Docs:8.0       │ Docs:8.5
└────────────────┴──────────────────┴────────────────┴──────────────
```

---

## 🎯 METAS POR ÁREA

### Testing
```
Frontend Unit Coverage:  2%  ──→ 50%  (Semana 2-4)
                        ▓▓░░░░░░░░  →  ████████████████
Backend Unit Coverage: 75%  ──→ 90%  (Semana 3)
                        ████████░░  →  █████████░
E2E Happy Path:        40%  ──→ 70%  (Semana 2)
                        ███░░░░░░░  →  ███████░░░
```

### Deployment
```
Deploy Frequency:      Manual  ──→  Every Commit (Semana 1)
Lead Time (PR→Prod):   1h      ──→  15 min (Semana 2)
Rollback Time:         30 min  ──→  5 min auto (Semana 2)
Uptime:                99%     ──→  99.5% (Semana 4)
```

### Code Quality
```
Backend Coesão:        ██░░  ──→  ████░  (Services refactor)
Frontend Test Cov:     ██░░  ──→  ██████ (Page + component tests)
Dead Code:             ░░░░░  ──→  ░░░░░  (Removed _legacy)
Tech Debt:             Medium ──→  Low   (After refactoring)
```

---

## 🏆 SUCCESS CRITERIA

✅ **Week 1 Complete:**
- [ ] Frontend deploy fix deployed
- [ ] Staging environment live
- [ ] Deploy automation working
- [ ] Deployment guide written

✅ **Week 2-4 Complete:**
- [ ] Frontend test coverage ≥ 30%
- [ ] All 14 pages covered by E2E
- [ ] Troubleshooting runbook live
- [ ] Services refactored

✅ **Month 2 Complete:**
- [ ] Frontend test coverage ≥ 50%
- [ ] Prometheus metrics live
- [ ] Design system documented
- [ ] Zero P0 issues open

---

## 📊 VELOCITY ESTIMATES

| Task | Story Points | Days | Team |
|------|--------------|------|------|
| P0.1 - Deploy fix | 1 | 0.25 | 1 DevOps |
| P0.2 - Page tests | 5 | 3 | 1 Frontend |
| P0.3 - Staging | 3 | 1 | 1 DevOps |
| P0.4 - Deploy auto | 3 | 1 | 1 DevOps |
| P1.1 - Component tests | 5 | 2 | 1 Frontend |
| P1.2 - Services refactor | 5 | 2 | 1 Backend |
| P1.3 - Runbooks | 3 | 2 | 1 DevOps |
| P1.4 - Prometheus | 3 | 2 | 1 Backend |
| **TOTAL** | **31 SP** | **13.25 days** | **Parallelizable: 2-3 devs** |

**Timeline:** 3 semanas (2 full-time devs) ou 4 semanas (1.5 devs)

---

## 💡 QUICK WINS

Implementáveis em < 1 hora cada:

- [ ] Add missing JSDoc to components
- [ ] Configure Lighthouse in CI
- [ ] Add TypeScript strict mode check
- [ ] Create pre-commit hook for linting
- [ ] Add .editorconfig for consistency

---

## 🚀 PRÓXIMOS PASSOS

1. **Hoje:** Revisar este documento com time
2. **Amanhã:** Criar issues no GitHub para cada P0
3. **Semana 1:** Executar P0 items
4. **Semana 2:** Executar P1 items
5. **Semana 3:** Validar produção

---

**Responsável:** DevOps/Backend Lead  
**Revisão:** 2026-06-25 (pós-P1)  
**Próximo passos:** Agendar kick-off meeting (30 min)
