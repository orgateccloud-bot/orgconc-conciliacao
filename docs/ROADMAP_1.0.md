# Roadmap OrgConc → 1.0

> **Estado atual:** v0.5.0 — **beta avançado em produção** (Railway + Supabase, RLS real por `org_id` enforçada).
> A fundação (multi-tenancy, auth, conciliação, laudo forense, CI/CD) está em nível de produção.
> O caminho para 1.0 é **abrangência + endurecimento**, não reconstrução.
> Base: avaliação multi-agente de 2026-06-09 (7 dimensões) + correções verificadas no código.

## Legenda
- 🤖 **Autônomo** — implemento direto (código/testes/docs).
- 🔑 **Requer você** — infra, credenciais ou decisão de negócio (preparo o que der no código).
- ⚠️ Todo merge na `main` = **deploy de produção** (Railway). PRs ficam verdes aguardando sua autorização explícita.

---

## P0 — Endurecimento & confiança (alto valor, baixo risco)
| # | Item | Tipo | Entrega |
|---|------|------|---------|
| 1 | ✅ **Cobertura de testes do frontend + gate no CI** (feito 2026-06-09) | 🤖 | 17/17 páginas + CommandPalette/AuditEventModal/AIInsightsPanel + `api.ts`; 249 testes; cobertura ~78% com `coverage.thresholds`; CI roda `test:coverage` |
| 2 | ✅ **Revogação de refresh token no logout** (verificado 2026-06-09) | 🤖 | já funcional (`revogar_por_hash` no logout; `logout-all`; reset/troca de senha). Adicionados testes (logout-all, idempotência) + docstring do modelo de revogação. *Denylist do access JWT por jti fica p/ P1.* |
| 3 | ✅ **Testes de rate-limit + headers `X-RateLimit-*`** (feito 2026-06-09) | 🤖 | `tests/test_rate_limit.py` (throttle 429 no CI); handler 429 customizado adiciona `X-RateLimit-Limit/Remaining/Reset` + `Retry-After` (sem `headers_enabled` global, que quebraria 34 endpoints) |
| 4 | ✅ **Policies RLS legadas limpas — APLICADO em prod** (2026-06-09) | 🤖 | migration 021 mergeada (#107) e verificada no banco vivo: `alembic_version=022`, 0 policies `*_org_policy` |
| 5 | ✅ **E2E profundo — feito** (2026-06-09, [#114](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/114)) | 🤖 | 3 specs novos com backend REAL via preview.proxy (upload→resultado+export, forense+laudo XLSX, erros de negócio); 24/24 estáveis em 2 rodadas |

## P1 — Fiscal & abrangência (valor de negócio)
| # | Item | Tipo | Entrega |
|---|------|------|---------|
| 6 | ✅ **Remover SERPRO** + generalizar p/ calculadora oficial (feito 2026-06-09) | 🤖 · 🔑 spec live | [#106](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/106): removeu OAuth2/Consumer-Key + vars SERPRO_*; `serpro_client.py`→`calculadora_client.py` (transporte aberto). Validação contra a API oficial live = 🔑 follow-up |
| 7 | ✅ **Apuração CBS/IBS idempotente — APLICADO em prod** (2026-06-09) | 🤖 | UNIQUE `(documento_id, versao_base)` + UPSERT (#107); constraint verificada no banco vivo |
| 8 | ❌ ~~Catálogo de anomalias AN-01..18~~ — **descartado** | — | taxonomia é do OrgAudi/rural (NFA-e SEFAZ-GO), não cabe no OrgConc (cruzamento entre contas). OrgConc já tem catálogo próprio em `matchers/forensics.py`. Caminho futuro: catálogo NATIVO |
| 9 | Jobs assíncronos p/ tarefas fiscais longas | 🔑 | worker/fila no Railway (calculadora/laudo deixam de ser bloqueantes) |

## P2 — Governança & escala (rumo ao 1.0 formal)
| # | Item | Tipo | Entrega |
|---|------|------|---------|
| 10 | ✅ **CHANGELOG (#105) + `/v1` dual-mount (#113)** | 🤖 | rotas de negócio também sob `/v1` (raiz preservada — zero breaking); auth/infra fora por design |
| 11 | ✅ **Staging dedicado — CRIADO** (2026-06-09) | 🔑→🤖 | Railway env `staging` + Postgres próprio + `web-staging` (deploy CLI); migrations validáveis fora de prod — ver `docs/STAGING.md` |
| 12 | 🟡 SLA/SLO — **metas propostas** (`docs/SLO.md`) | 🤖 preparo · 🔑 aprovar | 5 SLOs + orçamento de erro + resposta a incidente; ajustar a contrato |
| 13 | 🟡 Rotação de segredos — **runbook pronto** (`docs/ROTACAO_SEGREDOS.md`) | 🤖 preparo · 🔑 executar | procedimentos por segredo (JWT, app_orgconc, service token, Anthropic) + checklist |

---

## Progresso (2026-06-09)
Feito e em prod: **P0 #1,#2,#3** ([#104](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/104)) · **P1 #6** ([#106](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/106)) · **P2 #10 CHANGELOG** ([#105](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/105)) · 3.4 TS strict (anterior).
Preparado, HOLD (aplicar = 🔑): **P0 #4 + P1 #7** ([#107](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/107) draft).
Descartado: **P1 #8** (rural). Adiado: **P0 #5**, **2.4** refator laudo, **/v1**. 🔑 infra: **#9, #11, #12, #13** + spec live do #6.

## Critério de 1.0 (status — atualizado 2026-06-11) — **TODOS CUMPRIDOS** ✅
- [x] ✅ **Cobertura: backend 80.9%** (gate 80, #110) · **frontend 88.6%** (gate 86, #109) — ambos com gate no CI.
- [x] ✅ E2E: happy paths + fluxos profundos com backend real (#114; 24/24, exercitando `/v1` desde #119).
- [x] ✅ CBS/IBS sem SERPRO (#106) + apuração idempotente em prod (#107) + **pipeline validado AO VIVO na Calculadora oficial** (#127 — API aberta, gabarito do Manual RTC ao centavo).
- [x] ✅ Hardening P0: refresh revogável, rate-limit testado, RLS sem drift aplicado em prod (#107).
- [x] ✅ Staging criado e validando migrations (`docs/STAGING.md`) · rollback documentado (RUNBOOK) · **SLO VIGENTE** (aprovado 2026-06-10) · **rotação executada** (JWT/service/app_orgconc; restam ANTHROPIC_API_KEY/admin = só owner).
- [x] ✅ CHANGELOG (#105) + `/v1` dual-mount (#113) + frontend no `/v1` (#119) + **auth no `/v1`** (#126; só refresh/logout na raiz, pelo cookie).

> Refactor 2.4 do laudo completo (fases 1–3: #115, #118, #120) — cálculo 100% separado do render,
> todas com prova de regressão ao centavo nos dados reais (0 divergências em 262.939 células).
> P1 #9 (jobs assíncronos) entregue sem infra nova (#122/#124) — fila Postgres + worker nas réplicas.

> Histórico desta maratona (2026-06-09): #89–94 (dashboard), #95 (login), #96–98 (deps), #99 (bcrypt 5/sem passlib), #100 (Tailwind 4).
