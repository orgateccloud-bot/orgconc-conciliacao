# Planejamento — Dashboard Trust v3

**Origem:** redesign `dashboard_trust_v3_bundle.html` (Claude Design)
**Branch:** `claude/gifted-kare-475882`
**Plan file:** `C:\Users\Veloso\.claude\plans\https-claude-ai-design-p-07dcdb86-31dc-4-starry-treehouse.md`

---

## Status geral

| PR | Escopo | Status |
|----|--------|--------|
| **PR 1** | Backend foundation (audit + metrics + transacoes) | ✅ **Concluído** |
| **PR 2** | Frontend shell + Sidebar expansion | 🔲 Pendente |
| **PR 3** | KPIs + charts (liga endpoints MVP) | 🔲 Pendente |
| **PR 4** | Trust signals + audit timeline | 🔲 Pendente |
| **PR 5** | AI Insights + performance + E2E | 🔲 Pendente |

---

## PR 1 — Backend foundation ✅

**Entregues:**
- `migrations/versions/003_audit_events.py` — tabela com hash chain
- `api/db/models.py` — `AuditEvent`
- `api/services/audit.py` — `registrar_audit`, `verificar_cadeia`, `GENESIS_HASH`
- `api/db/audit_events.py` — CRUD eventos
- `api/db/metrics.py` — `agregar_kpis`, `serie_temporal`, `distribuicao_modo`, `heatmap_diario`, `listar_transacoes_recentes`
- `api/routers/metrics.py` — `/metrics/dashboard-bundle` (cache 60s/user), `/trend`, `/distribuicao`, `/heatmap`
- `api/routers/transacoes.py` — `/transacoes/recentes`
- `tests/test_audit.py` (10) + `tests/test_metrics.py` (13) — 23 testes novos

**Métricas:** 150 passed + 6 skipped, coverage 81% (mín 80%).

**Mudança vs plano original:** distribuição por *modo de conciliação* (simulacao/llm/multi), não por *formato de arquivo* (OFX/PDF/CSV) — formato não é persistido hoje. Se quiser por formato, requer migration adicional em `Conciliacao` para persistir a extensão.

**Pendente:** smoke test contra DB real (precisa Supabase ativo).

---

## PR 2 — Frontend shell + Sidebar expansion

**Objetivo:** colocar o esqueleto 3-colunas do novo design no ar com células ainda usando dados antigos. Build verde, navegação funcional.

**Critério de aceitação:**
- `npm run build` sem warnings TS
- `npm run dev` renderiza `/app/dashboard` em viewport ≥ 1280px com 3 colunas
- Sidebar global mostra grupos **Operação** e **Compliance** com novos itens
- Rotas `/anomalias`, `/transacoes`, `/auditoria`, `/seguranca` retornam página "Em breve" (não 404)
- KPIs antigos continuam renderizando dentro do novo grid (smoke test)
- Sidebar direita colapsa abaixo de `lg`

**Arquivos a editar:**
- `orgconc-react/src/components/Sidebar.tsx` — refatorar grupos para Operação/Compliance + adicionar items novos (Anomalias, Transações, Auditoria, Segurança) + security-card no rodapé
- `orgconc-react/src/App.tsx` — subir `max-w-[1400px]` → `max-w-[1600px]`; registrar 4 rotas placeholder
- `orgconc-react/src/pages/DashboardPage.tsx` — substituir pelo shell 3-colunas; manter conteúdo atual nas células principais provisoriamente
- `orgconc-react/tailwind.config.js` — adicionar tokens custom se faltar (`--glass-bg`, `--glass-blur`, `--aurora-*` se não existirem)

**Arquivos a criar:**
- `orgconc-react/src/pages/PlaceholderPage.tsx` — componente genérico "Em breve" (recebe título/descrição)
- `orgconc-react/src/components/dashboard/DashboardShell.tsx` — layout 3-colunas com slots
- `orgconc-react/src/components/dashboard/RightSidebar.tsx` — sidebar direita placeholder

**Tasks:**
1. Refatorar `Sidebar.tsx` (grupos novos + items + security-card)
2. Criar `PlaceholderPage.tsx` genérico
3. Atualizar `App.tsx` (max-w + 4 rotas novas)
4. Criar `DashboardShell.tsx` (CSS grid 3-col responsivo)
5. Criar `RightSidebar.tsx` (vazio, props futuras)
6. Atualizar `DashboardPage.tsx` (usar Shell, manter KPIs/charts atuais dentro)
7. Validar build + navegação manual

**Risco específico:** Sheet drawer mobile pode quebrar com novos items na Sidebar — validar com `preview_resize` em mobile.

---

## PR 3 — KPIs + charts (liga endpoints MVP)

**Objetivo:** dashboard mostrando dados reais do backend PR 1. KPIs com delta, line chart de tendência, donut de distribuição, heatmap diário, tabela transações recentes.

**Critério de aceitação:**
- KPIs renderizam números (não "—" nem NaN) consumindo `/metrics/dashboard-bundle`
- TrendChart e DistribuicaoChart renderizam em Recharts sem estouro de height
- Heatmap renderiza grid colorido (colapsa para 90d em mobile)
- Tabela de transações mostra ≥ 1 linha quando DB tem dados
- Erro handling: 503 mostra empty state amigável; 401 dispara logout (já existe)
- Sem regressão em testes Playwright atuais

**Arquivos a editar:**
- `orgconc-react/src/lib/api.ts` — adicionar `fetchDashboardBundle()`, `fetchTransacoesRecentes()`, tipos `DashboardBundle`, `KpiBlock`, `TrendPoint`, `DistribuicaoItem`, `HeatmapDay`, `TransacaoRecente`
- `orgconc-react/src/pages/DashboardPage.tsx` — wire dos endpoints, loading state, error handling
- `orgconc-react/src/components/dashboard/DashboardShell.tsx` — receber dados via props

**Arquivos a criar:**
- `orgconc-react/src/components/dashboard/KpiCard.tsx` — card com value, label, delta, sparkline opcional, ícone, accent bar
- `orgconc-react/src/components/dashboard/TrendChart.tsx` — Recharts `<LineChart>` com 2 séries (transações + anomalias)
- `orgconc-react/src/components/dashboard/DistribuicaoChart.tsx` — Recharts `<PieChart>` com `innerRadius` (donut) + legenda
- `orgconc-react/src/components/dashboard/Heatmap.tsx` — grid CSS Tailwind (53×7 desktop, 13×7 mobile)
- `orgconc-react/src/components/dashboard/TransacoesRecentes.tsx` — tabela responsiva com pills de status
- `orgconc-react/src/components/dashboard/DashboardSkeleton.tsx` — loading state

**Tasks:**
1. Estender `api.ts` com fetchers + tipos
2. `KpiCard.tsx` (sem sparkline ainda)
3. `TrendChart.tsx` (LineChart Recharts)
4. `DistribuicaoChart.tsx` (PieChart donut)
5. `Heatmap.tsx` (grid CSS, breakpoint lg)
6. `TransacoesRecentes.tsx`
7. `DashboardSkeleton.tsx` (placeholder durante load)
8. Wire em `DashboardPage.tsx` com `useEffect` + spinner
9. Validar com `preview_start` + screenshot

**Risco específico:** `Cliente`/`ApiError` já existem (reuso); mas Recharts `<PieChart>` precisa Cell por entrada — verificar versão `^3.8.1` API.

---

## PR 4 — Trust signals + audit timeline

**Objetivo:** score de confiança visual + trilha de auditoria com hashes verificáveis. Backend instrumentado com `registrar_audit` nos handlers críticos.

**Critério de aceitação:**
- Security ring renderiza com score derivado (0-100)
- Audit timeline mostra ≥ 1 evento com hash truncado clicável
- Modal de detalhes mostra payload + prev_hash + verificação de integridade visual
- Trust grid (3 cards) com métricas reais (taxa detecção, ciclos auditados)
- Compliance badges renderizam apenas itens confirmados (alinhar pontos abertos antes)
- Novo evento em `audit_events` ao fazer login, criar conciliação, criar/editar cliente

**Arquivos a editar (backend):**
- `api/routers/auth_routes.py` — chamar `registrar_audit("login.success", actor=user, payload={...})` após login bem-sucedido
- `api/routers/conciliacao.py` — `registrar_audit("conciliacao.criar", resource_id=rid, payload={"modo": ..., "total_tx": ...})` ao final de cada handler
- `api/routers/clientes.py` — `registrar_audit("cliente.criar"|"cliente.atualizar", resource_id=cid, payload=...)`
- `api/main.py` — registrar `audit_router` (novo)

**Arquivos a criar (backend):**
- `api/routers/audit.py` — `GET /audit/timeline?limit=20`, `GET /audit/eventos/{id}` (detalhe com payload)
- `api/routers/metrics.py` — adicionar `GET /metrics/trust-score` (cálculo: % conciliações sem erro 30d + dias desde última falha + % http 2xx)

**Arquivos a editar (frontend):**
- `orgconc-react/src/lib/api.ts` — `fetchAuditTimeline()`, `fetchTrustScore()`, tipos `AuditEvent`, `TrustScore`

**Arquivos a criar (frontend):**
- `orgconc-react/src/components/dashboard/SecurityRing.tsx` — SVG circle 150×150 com `strokeDasharray` animado
- `orgconc-react/src/components/dashboard/TrustGrid.tsx` — 3 cards com ícone+métrica+meta
- `orgconc-react/src/components/dashboard/AuditTimeline.tsx` — lista de eventos com dot colorido por severidade
- `orgconc-react/src/components/dashboard/AuditEventModal.tsx` — Radix Dialog com payload JSON + hash chain
- `orgconc-react/src/components/dashboard/ComplianceBadges.tsx` — lista estática (depende dos pontos abertos)

**Tasks:**
1. Endpoint `/metrics/trust-score` + testes
2. Endpoints `/audit/timeline` + `/audit/eventos/{id}` + testes
3. Instrumentar 3 routers com `registrar_audit` + testes
4. `SecurityRing.tsx` (SVG animado)
5. `TrustGrid.tsx` (cards)
6. `AuditTimeline.tsx` + `AuditEventModal.tsx`
7. `ComplianceBadges.tsx` (após decisão dos pontos abertos)
8. Wire no DashboardPage
9. Validar coverage continua ≥ 80%

**Riscos específicos:**
- Hash chain pode quebrar se múltiplas inserções concorrentes (race condition no `_buscar_ultimo_hash`). → Mitigação: usar `SELECT ... FOR UPDATE` no buscar último ou serializar em fila Redis.
- Modal de payload pode vazar PII se payload contiver dados sensíveis. → Mitigação: passar payload pelo `mask_pii` antes de retornar no endpoint.

---

## PR 5 — AI Insights + performance + polish + E2E

**Objetivo:** completar o dashboard com insights da IA, painel de performance dos modelos, feed de atividade na sidebar direita, e suíte E2E completa.

**Critério de aceitação:**
- AI Insights renderiza ≥ 1 card (success/warn/info) com texto gerado pela Claude
- Performance Modelos mostra latência média por modelo
- Activity Feed na sidebar direita mostra últimos N eventos
- Indicadores (goals/progress bars) mostram trust score + outras métricas
- Topbar com trust badges (LGPD etc) renderizadas
- Spec Playwright `dashboard.spec.ts` passa em CI
- Dark mode validado em toda a página

**Arquivos a editar (backend):**
- `api/db/models.py` — adicionar `Conciliacao.usage_latency_ms`
- `api/services/db_persistence.py` — persistir `latency_ms` no `salvar_no_banco`
- `api/routers/conciliacao.py` — capturar latência da chamada Claude (já tem `time.perf_counter` em alguns lugares)

**Arquivos a criar (backend):**
- `migrations/versions/004_conciliacoes_latency.py` — `ADD COLUMN usage_latency_ms INT`
- `api/db/ai_insights_cache.py` — cache em tabela `ai_insights_cache(user_sub, ts, payload_jsonb)`; nova migration `005_ai_insights_cache.py` se for em Postgres
- `api/services/ai_insights.py` — `gerar_insights_dashboard(db, actor)` que chama Claude com prompt agregado
- `api/routers/ai.py` — `GET /ai/insights/dashboard?refresh=false` (com cache 24h por user)
- `api/routers/metrics.py` — adicionar `GET /metrics/modelos` (latência média 30d)
- `api/routers/activity.py` — `GET /activity/feed?limit=10` (view sobre audit_events)

**Arquivos a editar (frontend):**
- `orgconc-react/src/lib/api.ts` — `fetchAiInsights()`, `fetchPerformanceModelos()`, `fetchActivityFeed()`, tipos
- `orgconc-react/src/components/dashboard/RightSidebar.tsx` — preencher com Activity + Indicadores
- `orgconc-react/src/components/Topbar.tsx` — adicionar trust badges (LGPD), placeholder search ⌘K
- `orgconc-react/src/pages/DashboardPage.tsx` — wire dos 3 endpoints novos

**Arquivos a criar (frontend):**
- `orgconc-react/src/components/dashboard/AIInsightsPanel.tsx` — 3 cards de insight; botão "Atualizar" que chama com `?refresh=true`
- `orgconc-react/src/components/dashboard/PerformanceModelos.tsx` — Recharts BarChart horizontal + pills (Haiku/Sonnet/Opus)
- `orgconc-react/src/components/dashboard/ActivityFeed.tsx` — lista timeline para sidebar direita
- `orgconc-react/src/components/dashboard/IndicadoresGoals.tsx` — 3 progress bars (taxa, precisão, compliance)
- `orgconc-react/e2e/dashboard.spec.ts` — spec Playwright

**Tasks:**
1. Migration `004` (usage_latency_ms) + persistir em `db_persistence`
2. Migration `005` (ai_insights_cache) + `ai_insights.py` service
3. Endpoint `/ai/insights/dashboard` + testes
4. Endpoint `/metrics/modelos` + testes
5. Endpoint `/activity/feed` + testes
6. `AIInsightsPanel.tsx` (com botão refresh)
7. `PerformanceModelos.tsx` (BarChart horizontal)
8. `ActivityFeed.tsx` na sidebar direita
9. `IndicadoresGoals.tsx`
10. Topbar com badges
11. Spec Playwright completo
12. Dark mode pass: verificar todos os tokens
13. Validar coverage final ≥ 80%

**Riscos específicos:**
- Claude chamada em cada page load = custo. Cache obrigatório antes de release.
- Recharts BarChart horizontal pode precisar `layout="vertical"` — verificar API.
- Playwright spec pode flakiar com loading async — usar `await expect(...).toBeVisible({timeout: 10000})`.

---

## Endpoints — visão consolidada

| Endpoint | Método | PR | Cache | Status |
|----------|--------|----|------|--------|
| `/metrics/dashboard-bundle` | GET | PR 1 | 60s/user | ✅ |
| `/metrics/trend` | GET | PR 1 | — | ✅ |
| `/metrics/distribuicao` | GET | PR 1 | — | ✅ |
| `/metrics/heatmap` | GET | PR 1 | — | ✅ |
| `/transacoes/recentes` | GET | PR 1 | — | ✅ |
| `/metrics/trust-score` | GET | PR 4 | 300s/global | 🔲 |
| `/audit/timeline` | GET | PR 4 | — | 🔲 |
| `/audit/eventos/{id}` | GET | PR 4 | — | 🔲 |
| `/metrics/modelos` | GET | PR 5 | 60s/global | 🔲 |
| `/ai/insights/dashboard` | GET | PR 5 | 24h/user | 🔲 |
| `/activity/feed` | GET | PR 5 | 60s/global | 🔲 |

## Migrations — ordem

| Migration | Tabela | PR | Status |
|-----------|--------|----|----|
| `003_audit_events` | `audit_events` | PR 1 | ✅ |
| `004_conciliacoes_latency` | `conciliacoes ADD COLUMN` | PR 5 | 🔲 |
| `005_ai_insights_cache` | `ai_insights_cache` | PR 5 | 🔲 |

---

## Pontos abertos (decisão necessária)

### Antes do PR 4
**1. Compliance badges reais (ComplianceBadges.tsx)**
O design tem LGPD, SOC 2, ISO 27001, PCI-DSS, BACEN. Já está confirmado: **remover ISO 27001**. Falta decidir:

| Badge | Tipo | Sugestão |
|-------|------|----------|
| LGPD | Autodeclaração de conformidade | ✅ Manter — produto está em conformidade |
| SOC 2 | Certificação externa | ⚠️ Remover se não há auditoria SOC 2 ativa |
| PCI-DSS | Certificação para processar cartões | ⚠️ Remover se não processa cartões |
| BACEN | Registro/autorização BACEN | ⚠️ Remover se não é instituição autorizada |

**Risco regulatório:** exibir badge implica certificação real — pode ser interpretado como propaganda enganosa em produto financeiro. Recomendação cautelosa: **só LGPD** até houver lastro documental.

### Antes do PR 5
**2. AI Insights — opt-in vs auto-refresh**
- **Manual:** botão "Gerar insights" → chama Claude on-demand. Custo controlado, UX exige clique.
- **Auto-diário:** primeira visita do dia carrega cached (24h TTL). Custo previsível, UX zero-friction.
- **Híbrido (recomendado):** auto-carrega cache do dia se existir; botão "Atualizar" força refresh.

**3. Search ⌘K na Topbar**
- **Agora (PR 5):** placeholder visual não-funcional (campo + atalho exibido, click não faz nada).
- **Fase 2 (PR 6):** implementar command palette real (busca clientes/conciliações/relatórios).
- Recomendação: placeholder no PR 5; backlog para PR 6.

---

## Cronograma sugerido

```
PR 1  ━━━━━━━━━━━━━━━  ✅ Concluído (commit local)
PR 2  ━━━━━━━━━━━     [shell + sidebar; sem dependências de DB]
PR 3  ━━━━━━━━━━━━━━ [requer DB ativo para validar dados reais; senão usa fixtures]
       ▲ ponto de revisão: alinhar pontos abertos #1
PR 4  ━━━━━━━━━━━━━━━ [requer endpoints + UI; mais pesado]
       ▲ ponto de revisão: alinhar pontos abertos #2 e #3
PR 5  ━━━━━━━━━━━━━━━━━━ [maior; envolve Claude API + E2E]
```

**Recomendação:** rodar PR 2 e PR 3 em sequência sem pausa (mesma área, mesmas decisões); pausar antes de PR 4 para alinhar compliance badges; pausar antes de PR 5 para confirmar AI Insights opt-in.

---

## Reuso garantido (não recriar)

**Backend:**
- `apiFetch<T>` em `orgconc-react/src/lib/api.ts:37`
- `ApiError` (já dispara logout em 401)
- `current_user` dependency + `limiter` SlowAPI
- `logging_estruturado` (request_id, PII masking)
- `DB_DISPONIVEL` flag + padrão 503
- `_serializar` em `conciliacoes_list.py:15` (padrão de serialização)
- `registrar_audit` agora disponível para qualquer router (PR 1)

**Frontend:**
- Componentes Radix em `orgconc-react/src/components/ui/`
- `cn` em `@/lib/utils`
- Tokens Tailwind `brand.*` + CSS vars `--d-*`
- Sonner para toasts
- `useAuth`, `useTheme` hooks

---

## Verificação por PR

| PR | Comando |
|----|---------|
| PR 1 | ✅ `pytest tests/ --cov=api --cov-fail-under=80` |
| PR 2 | `cd orgconc-react && npm run build` + `npm run dev` (visual) |
| PR 3 | acima + `curl /metrics/dashboard-bundle` + preview screenshot |
| PR 4 | acima + `pytest` + verificar audit_events na tabela após login |
| PR 5 | acima + `npm run test:e2e -- dashboard.spec.ts` |

**Smoke manual final (após PR 5):** subir uvicorn + npm dev → login → criar conciliação OFX → voltar /dashboard → conferir que (a) KPI "Conciliações" incrementou, (b) Heatmap mostra célula hoje, (c) Trust score atualizou, (d) Audit timeline tem novo evento, (e) AI Insights mostra cards.
