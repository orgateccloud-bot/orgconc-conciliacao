# Planejamento de Execução — OrgConc → 1.0

> **Base:** remapeamento de 2026-06-09 ([`PROJETO_MAPEAMENTO_COMPLETO.md`](../PROJETO_MAPEAMENTO_COMPLETO.md))
> cruzado com o [`ROADMAP_1.0.md`](ROADMAP_1.0.md).
> **Estado:** v0.5.0 production-ready multi-tenant · nota 7.8/10 · meta 1.0 ≈ 8.5/10.
> **Regra de deploy:** todo merge na `main` = deploy de produção (Railway). PRs ficam verdes
> aguardando autorização explícita por PR.

## Legenda
- 🤖 **Autônomo** — implemento direto (código/testes/docs).
- 🔑 **Requer você** — infra, credenciais ou decisão de negócio (preparo o que der no código).
- Esforço: **P** ≤ meio dia · **M** 1–2 dias · **G** 3–5 dias.

---

## Sprint 1 — Endurecimento P0 (1–2 semanas) · destrava confiança

| # | Item | Tipo | Esf. | Critério de aceite | Origem | Status |
|---|------|------|------|--------------------|--------|--------|
| 1.1 | **Cobertura frontend + gate no CI** | 🤖 | G | `vitest --coverage` com threshold (alvo 70%); testes para as páginas sem cobertura (AuditoriaForense, Usuarios, Upload, Matchers, Laudo, Cartas, Gaps, Contratos, Guias, Relatorios, Configuracoes, Login) e para CommandPalette/AIInsightsPanel; CI falha abaixo do threshold | Roadmap P0 #1 · Achado A4 | ✅ **Feito** |
| 1.2 | **Revogação de refresh token no logout** | 🤖 | M | `POST /auth/logout` invalida o refresh token no DB na hora; teste cobre revogação | Roadmap P0 #2 · Achado A7 | ✅ **Feito** (já funcional; +testes +docstring) |
| 1.3 | **Testes de rate-limit + headers `X-RateLimit-*`** | 🤖 | M | respostas 429 com `Retry-After`/limite; teste do throttle no CI | Roadmap P0 #3 | ✅ **Feito** (handler 429 custom) |
| 1.4 | **E2E mais profundo** | 🤖 | G | specs Playwright: upload OFX→resultado, fluxo de auditoria forense, erros de negócio | Roadmap P0 #5 | ⚠️ Adiado (risco de flakiness no CI — operações fiscais/timeout) |

**Saída do Sprint 1:** gate de cobertura frontend ativo, sessão revogável, throttle testado, E2E cobrindo
fluxos críticos. **Nota projetada: ~8.1/10.**

### ✅ 1.1 — Resultado (2026-06-09)
- **+16 arquivos de teste** (12 páginas + CommandPalette/AIInsightsPanel/AuditEventModal + cliente `api.ts`),
  **+209 casos** → suíte de **249 testes, todos verdes**.
- **Cobertura:** stmts 43→**75.8%** · lines 45→**78.1%** · funcs 34→**72.5%** · branches 38→**65.1%**
  (`api.ts` 21→**94%**). Meta ≥70% superada.
- **Gate:** `coverage.thresholds` em `vitest.config.ts` (stmts 73 / branches 62 / funcs 68 / lines 75) +
  job de CI agora roda `npm run test:coverage`. `tsc --noEmit` verde; `coverage/` gitignored.
- **Follow-up p/ chegar a 80% (critério 1.0):** aprofundar 4 páginas com testes rasos pré-existentes
  (Clientes 33%, Conciliacao 35%, Conformidade 35%, RiscoTributario 45%) e o componente AuditTimeline (31%).

---

## Sprint 2 — Fiscal & abrangência P1 (2–4 semanas) · valor de negócio

| # | Item | Tipo | Esf. | Critério de aceite | Origem | Status |
|---|------|------|------|--------------------|--------|--------|
| 2.1 | **Remover SERPRO** + apontar calculadora CBS/IBS p/ API oficial (portal Tributos) | 🤖 remoção · 🔑 spec do endpoint live | G | remove auth OAuth2/Consumer-Key SERPRO e naming; mantém transporte genérico `CALCULADORA_BASE_URL` (`consumo.tributos.gov.br`); atualiza config/testes/docs | Roadmap P1 #6 · Achado A1 | ✅ **Feito** ([#106](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/106)) · validação live = 🔑 |
| 2.2 | **Persistir apuração CBS/IBS (idempotência)** | 🤖 preparo · 🔑 aplicar | M | UNIQUE `(documento_id, versao_base)` + UPSERT em `salvar_apuracao` (migration 022) | Roadmap P1 #7 | 🟡 **Preparado, HOLD** ([#107](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/107)) |
| 2.3 | **Catálogo de anomalias AN-01..18 no laudo** | — | G | — | Roadmap P1 #8 | ❌ **Descartado** — taxonomia rural/OrgAudi, não cabe no OrgConc (ver §Verificação) |
| 2.4 | **Refator `services/laudo_forense.py`** (2.089 LOC) | 🤖 | G | extrai camada de cálculo do render; saída idêntica ao centavo (regressão LOCAR verde) | Achado A6 · Mapa §1.4 | ⚠️ Adiado (risco alto; revisão humana) |
| 2.5 | **Limpar policies RLS legadas `*_org_policy`** | 🤖 preparo · 🔑 aplicar | P | migration `DROP POLICY` (021); aplicação coordenada | Roadmap P0 #4 · Achado A5 | 🟡 **Preparado, HOLD** ([#107](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/107)) |

**Saída do Sprint 2:** CBS/IBS sem SERPRO (✅ em prod), idempotência + RLS limpa preparadas (HOLD).
2.3 descartado, 2.4 adiado. **Nota projetada após aplicar #107: ~8.4/10.**

---

## Sprint 3 — Governança & escala P2 (1–2 meses) · rumo ao 1.0 formal

| # | Item | Tipo | Esf. | Critério de aceite | Origem | Status |
|---|------|------|------|--------------------|--------|--------|
| 3.1a | **CHANGELOG** | 🤖 | P | Keep a Changelog + SemVer; histórico 0.5.0 + [Não lançado] | Roadmap P2 #10 | ✅ **Feito** ([#105](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/105)) |
| 3.1b | **Versionamento de API (`/v1`)** | 🤖 | M | rotas sob `/v1` (dual-mount p/ não quebrar o frontend) | Roadmap P2 #10 | ⚠️ Adiado (breaking — confirmar abordagem) |
| 3.2 | **Staging dedicado** | 🔑 | G | Railway env + Supabase branch; migrations validadas antes de prod | Roadmap P2 #11 · Mapa §4.2 | ⛔ 🔑 infra |
| 3.3 | **Jobs assíncronos p/ tarefas fiscais longas** | 🔑 | G | worker/fila no Railway; calculadora/laudo não-bloqueantes | Roadmap P1 #9 | ⛔ 🔑 infra |
| 3.4 | **TypeScript strict no frontend** | 🤖 | M | `noUnusedLocals/Parameters: true`; `tsc --noEmit` bloqueante no CI | Mapa §2.4 | ✅ **Já feito** (2026-06-03, commit 7166a497) |
| 3.5 | **SLA/SLO + rotação de segredos** | 🔑 | M | metas documentadas + Sentry/logs em prod; rotação do JWT/chaves | Roadmap P2 #12, #13 | ⛔ 🔑 infra/decisão |

**Saída do Sprint 3:** CHANGELOG ✅ e TS strict ✅; /v1, staging, jobs, SLO/rotação pendentes (decisão/infra).

---

## Verificação de estado (2026-06-09) — antes de implementar os Sprints 2–3

Varredura read-only (10 agentes) cruzando roadmap × código. Achados que mudam o plano:

| Item | Estado real | Decisão |
|------|-------------|---------|
| 3.4 TS strict | ✅ **já feito** (2026-06-03) | nada a fazer; doc corrigido |
| 1.2 / 1.3 | ✅ **feito neste ciclo** (ver Sprint 1) | mergeável |
| 2.1 SERPRO | transporte já genérico; falta remover OAuth2/Consumer-Key. **Risco médio** (fiscal/prod; substituto oficial 🔑 sem spec/credencial) | preparar removível; **confirmar antes de prod** |
| 2.2 CBS/IBS | já persiste; falta **idempotência** (UNIQUE `(documento_id, versao_base)` + UPSERT) → migration | preparo 🤖; **aplicar migration = 🔑** (CI não roda migrations) |
| 2.3 Catálogo AN-01..18 | ⚠️ **taxonomia não existe no OrgConc** — é do OrgAudi/rural (skill-rural, GIEF/SEFAZ-GO). Hoje só 3 flags. | **bloqueado por decisão:** confirmar se o catálogo rural se aplica e qual a fonte |
| 2.4 Refator laudo | monólito `gerar_laudo_workbook` (976 linhas). **Risco alto** (reproduz laudo LOCAR ao centavo; dados sigilosos) | fazer incremental c/ regressão; **revisão humana antes de prod** |
| 2.5 RLS legadas | DROP já está em `org_isolation.sql`; falta migration Alembic 021 formal | preparo 🤖; **aplicar = 🔑** |
| 3.1 /v1 + CHANGELOG | **breaking** (16 routers + 40+ paths no frontend). CHANGELOG trivial | CHANGELOG 🤖; **/v1 = confirmar abordagem** (dual-mount p/ não quebrar) |

> **Resumo:** Sprint 1 (P0) entregue e mergeado. SERPRO removido (#106) e CHANGELOG (#105) em prod.
> Idempotência CBS/IBS + RLS legadas preparadas e em HOLD (#107, aplicação 🔑). 2.3 descartado;
> 2.4 / 3.1-/v1 / 1.4 adiados (risco); staging/jobs/SLO/rotação dependem de você.

## Execução 2026-06-09 (2ª rodada — modo automático com permissão total)

| Status | Item | PR / evidência |
|--------|------|----------------|
| ✅ Aplicado em prod + verificado no banco | P0 #4 RLS legadas + P1 #7 idempotência CBS/IBS | [#107](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/107) — `alembic=022`, constraint criada, 0 policies |
| ✅ Mergeado | P2 #10 `/v1` dual-mount (auth/infra fora por design) | [#113](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/113) |
| ✅ Mergeado | P0 #5 E2E profundo com backend real (24/24, 2 rodadas) | [#114](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/114) |
| ✅ Mergeado | 2.4 fase 1 — `preparar_calculo_laudo` + determinismo aba 7 (prova LOCAR ao centavo) | [#115](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/115) |
| ✅ Mergeado | **Bugfix**: anualizado do Sumário sombreado pelo loop de MEIs (regressão do 59401c1e) | [#116](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/116) |
| ✅ Criado | P2 #11 staging Railway (env+Postgres+web-staging) | `docs/STAGING.md` |
| 🟡 Proposto (🔑 aprovar) | P2 #12 SLO · P2 #13 rotação | `docs/SLO.md` · `docs/ROTACAO_SEGREDOS.md` |

## Execução 2026-06-10 (3ª rodada — merges liberados por OK explícito)

| Status | Item | PR / evidência |
|--------|------|----------------|
| ✅ Mergeado em prod | 2.4 fase 2 — agregados das abas (risco/fluxos/MEIs/tributário/pós-baixa/transf. internas) na fase pura; prova ao centavo 0/262.939 células | [#118](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/118) |
| ✅ Mergeado em prod | Frontend migrado p/ `/v1` (rotas de negócio; `/auth` na raiz pelo cookie de refresh); vitest 345 + E2E real 24/24 | [#119](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/119) |
| ✅ Mergeado em prod | 2.4 fase 3 — risk score por transação anexado na fase pura (`_anexar_risco_disps`); abas 5/6 só renderizam; **desmembramento cálculo×render COMPLETO**; prova ao centavo 0/262.939 | [#120](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/120) |
| ✅ Mergeado em prod | **P1 #9 jobs assíncronos SEM infra nova**: fila em Postgres (migration 023 + RLS `worker_access`) + worker asyncio nas réplicas (SKIP LOCKED); `POST /fiscal/laudo/async` + `GET /jobs/*`; **validado no staging ponta-a-ponta** (migration no preDeploy + smoke: submit → CONCLUIDO <3s → XLSX 20.599 bytes) | [#122](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/122) |
| ✅ Mergeado em prod | UI do laudo via fila (fases na UI + fallback síncrono em 503/403); E2E real exercitou o fallback | [#124](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/124) |
| ✅ Mergeado em prod | Observabilidade do incidente: ping de DB com log do erro real + sonda de banco no monitor (30min) | [#123](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/123) |
| 🔧 Incidente resolvido | Prod ~32h sem DB no runtime (senha `app_orgconc` divergente — rotação parcial); reset via owner + variável + redeploy; senha do `app_orgconc` portanto JÁ rotacionada | post-mortem em `docs/postmortems/` · RUNBOOK §5 |
| ✅ **Validação live da calculadora** — a API oficial é ABERTA (descoberta 2026-06-10: sem credencial!); pipeline reproduziu o gabarito do Manual RTC na produção oficial (CBS R$ 36,00 + IBS-UF R$ 4,00, base V0033, 9/9 checks); ajustes do contrato real (`dhFatoGerador`, pre-flight `dados-abertos/versao`); p/ volume: componente offline self-hosted (recomendação RFB) | [#127](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/127) |
| 🟢 PR aberto | Migração do `/auth` p/ `/v1` SEM quebrar sessões: dual-mount completo; só `refresh`/`logout` ficam na raiz (únicos que leem o cookie httpOnly path=/auth) | [#126](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/126) |
| ✅ Aprovado pelo owner | **SLO VIGENTE** (P2 #12): 5 metas de `docs/SLO.md` aprovadas 2026-06-10 | `docs/SLO.md` |
| ✅ Executado em prod | **Rotação de segredos** (P2 #13): JWT_SECRET + AUTH_TOKEN rotacionados 2026-06-10 (sem downtime) + app_orgconc (incidente). Pendente só do owner: ANTHROPIC_API_KEY · ADMIN_SENHA_HASH | CHANGELOG §Segurança |
| ⏭️ Restante (🔑 somente owner) | rotacionar ANTHROPIC_API_KEY (console Anthropic) e ORGCONC_ADMIN_SENHA_HASH · (opcional) hospedar componente offline da calculadora p/ volume | — |

## Execução 2026-06-09 — itens → PRs

| Status | Itens | PR |
|--------|-------|----|
| ✅ Mergeado em prod | P0 #1,#2,#3 (Sprint 1) | [#104](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/104) |
| ✅ Mergeado em prod | P2 #10 CHANGELOG | [#105](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/105) |
| ✅ Mergeado em prod | P1 #6 remoção SERPRO | [#106](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/106) |
| 🟡 HOLD (aplicar = 🔑) | P0 #4 (RLS 021) + P1 #7 (idempotência 022/UPSERT) | [#107](https://github.com/orgateccloud-bot/orgconc-conciliacao/pull/107) (draft) |
| ✅ Já feito antes | 3.4 TS strict | (2026-06-03) |
| ❌ Descartado | P1 #8 catálogo AN-01..18 (rural/OrgAudi) | — |
| ⚠️ Adiado (risco) | P0 #5 E2E profundo · 2.4 refator laudo · 3.1 /v1 | — |
| ⛔ 🔑 infra/decisão | P1 #9 jobs · P2 #11 staging · #12 SLO · #13 rotação | — |

---

## Itens 🔑 (dependem de você — infra/credenciais/decisão)
- **2.1 (parte live):** spec do endpoint da API oficial do portal Tributos.
- **3.2 Staging:** provisionar Railway env + Supabase branch.
- **3.3 Jobs assíncronos:** worker/fila no Railway.
- **3.5 SLA/SLO + rotação:** metas de negócio + acesso a key management.

## Próximos passos (ordem sugerida)
1. **Aplicar #107** (quando você liberar): conferir `alembic heads` × base viva + revisar dedup da 022 → tirar do draft.
2. **2.4 refator do laudo** (com regressão verde) e **3.1 /v1** (dual-mount) — quando aprovados.
3. **P0 #5 E2E profundo** — aceitar/mitigar a flakiness no CI.
4. Itens 🔑 (staging, jobs, SLO, rotação, validação live da calculadora) conforme infra/credenciais.

## Critério de 1.0 (do roadmap, com status atual)
- [x] ✅ **Cobertura: backend 80.2%** (gate 80, #110) · **frontend 88.6%** (gate 86, #109) — ambos com gate no CI (2026-06-09).
- [ ] E2E cobrindo conciliação, laudo, auth — *parcial* (happy paths; profundo adiado).
- [~] CBS/IBS sem SERPRO ✅ (#106) + apuração persistida idempotente — *preparada, HOLD* (#107).
- [~] Hardening P0: ✅ refresh revogável, ✅ rate-limit testado; RLS sem drift *preparado, HOLD* (#107).
- [ ] Staging + rollback + SLA/SLO documentados — 🔑.
- [~] CHANGELOG ✅ (#105) + versionamento de API `/v1` — *adiado*.

---

**Gerado:** 2026-06-09, a partir do remapeamento completo. Atualizar ao fim de cada sprint.
