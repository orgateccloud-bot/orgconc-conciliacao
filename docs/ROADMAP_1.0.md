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
| 4 | 🟡 **Limpar policies RLS legadas inertes** (preparado, HOLD) | 🤖 preparo · 🔑 aplicar | migration 021 (`DROP POLICY` idempotente, 11 tabelas) em [#107](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/107) (draft) — aplicação coordenada (merge dispara alembic) |
| 5 | ⚠️ E2E mais profundo — **adiado** | 🤖 | risco de flakiness no CI (operações fiscais/timeout); 4 specs atuais verdes |

## P1 — Fiscal & abrangência (valor de negócio)
| # | Item | Tipo | Entrega |
|---|------|------|---------|
| 6 | ✅ **Remover SERPRO** + generalizar p/ calculadora oficial (feito 2026-06-09) | 🤖 · 🔑 spec live | [#106](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/106): removeu OAuth2/Consumer-Key + vars SERPRO_*; `serpro_client.py`→`calculadora_client.py` (transporte aberto). Validação contra a API oficial live = 🔑 follow-up |
| 7 | 🟡 **Persistir apuração CBS/IBS (idempotência)** — preparado, HOLD | 🤖 preparo · 🔑 aplicar | UNIQUE `(documento_id, versao_base)` + UPSERT (migration 022) em [#107](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/107) (draft) |
| 8 | ❌ ~~Catálogo de anomalias AN-01..18~~ — **descartado** | — | taxonomia é do OrgAudi/rural (NFA-e SEFAZ-GO), não cabe no OrgConc (cruzamento entre contas). OrgConc já tem catálogo próprio em `matchers/forensics.py`. Caminho futuro: catálogo NATIVO |
| 9 | Jobs assíncronos p/ tarefas fiscais longas | 🔑 | worker/fila no Railway (calculadora/laudo deixam de ser bloqueantes) |

## P2 — Governança & escala (rumo ao 1.0 formal)
| # | Item | Tipo | Entrega |
|---|------|------|---------|
| 10 | 🟢 CHANGELOG ✅ ([#105](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/105)) · ⚠️ `/v1` adiado | 🤖 | CHANGELOG (Keep a Changelog + SemVer) em prod; `/v1` é breaking (16 routers + 40+ paths) — confirmar abordagem dual-mount |
| 11 | 🟢 Staging dedicado ✅ (parcial) | 🔑 | Railway env `staging` + Postgres + `web-staging` NO AR (validar migrations lá antes de prod — ver DEPLOY.md §2); falta Supabase branch p/ paridade de RLS |
| 12 | SLA/SLO + observabilidade pós-deploy | 🔑 | metas + Sentry/logs centralizados confirmados em prod |
| 13 | Rotação de segredos / key management | 🔑 | rotação do JWT secret + chaves |

---

## Progresso (2026-06-09)
Feito e em prod: **P0 #1,#2,#3** ([#104](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/104)) · **P1 #6** ([#106](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/106)) · **P2 #10 CHANGELOG** ([#105](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/105)) · 3.4 TS strict (anterior).
Preparado, HOLD (aplicar = 🔑): **P0 #4 + P1 #7** ([#107](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/107) draft).
Descartado: **P1 #8** (rural). Adiado: **P0 #5**, **2.4** refator laudo, **/v1**. 🔑 infra: **#9, #11, #12, #13** + spec live do #6.

## Critério de 1.0 (status)
- [x] ✅ **Cobertura: backend 80.2%** (gate 80, #110) · **frontend 88.6%** (gate 86, #109) — ambos com gate no CI.
- [~] E2E: happy paths ✅; fluxos profundos (upload→resultado, auditoria) adiados.
- [~] CBS/IBS sem SERPRO ✅ (#106) + apuração persistida idempotente — preparada (HOLD #107).
- [~] Hardening P0: ✅ refresh revogável, ✅ rate-limit testado; RLS sem drift preparado (HOLD #107).
- [ ] Staging + rollback + SLA/SLO documentados — 🔑.
- [~] CHANGELOG ✅ (#105) + versionamento `/v1` — adiado.

> Histórico desta maratona (2026-06-09): #89–94 (dashboard), #95 (login), #96–98 (deps), #99 (bcrypt 5/sem passlib), #100 (Tailwind 4).
