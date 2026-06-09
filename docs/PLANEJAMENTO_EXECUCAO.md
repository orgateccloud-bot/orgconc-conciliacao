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

| # | Item | Tipo | Esf. | Critério de aceite | Origem |
|---|------|------|------|--------------------|--------|
| 2.1 | **Remover SERPRO** + apontar calculadora CBS/IBS p/ API oficial (portal Tributos) | 🤖 remoção · 🔑 spec do endpoint live | G | remove auth OAuth2/Consumer-Key SERPRO e naming dos 5 arquivos (`config.py`, `infra/__init__.py`, `routers/fiscal.py`, `services/calculadora_cbs_ibs.py`, `services/serpro_client.py`); mantém transporte genérico `CALCULADORA_BASE_URL` (`consumo.tributos.gov.br`); atualiza config/testes/docs | Roadmap P1 #6 · Achado A1 |
| 2.2 | **Persistir apuração CBS/IBS** | 🤖 | M | `POST /fiscal/apurar` grava `documento_id` + `versao_base` + `resultado` + `payload_hash` em `apuracao_cbs_ibs` (migrations 013/014/018 já existem) | Roadmap P1 #7 |
| 2.3 | **Catálogo de anomalias AN-01..18 no laudo** | 🤖 | G | laudo gera alertas estruturados do catálogo (hoje só 3 flags: MEI_SEM_CTE, REDE_FROTA_TYPE, PARTE_RELACIONADA) | Roadmap P1 #8 |
| 2.4 | **Refator `services/laudo_forense.py`** (2.089 LOC) | 🤖 | G | extrai camada de cálculo (agregação/heatmap) do render (XLSX/MD/HTML/PDF); comportamento idêntico ao centavo (testes de regressão do laudo LOCAR verdes) | Achado A6 · Mapa §1.4 |
| 2.5 | **Limpar 3 policies RLS legadas `*_org_policy`** | 🤖 preparo · 🔑 aplicar | P | migration de `DROP POLICY` revisável; aplicação em prod coordenada | Roadmap P0 #4 · Achado A5 |

**Saída do Sprint 2:** CBS/IBS sem SERPRO e persistida, laudo com catálogo de anomalias, fat file
desmembrado, RLS sem drift. **Nota projetada: ~8.5/10.**

---

## Sprint 3 — Governança & escala P2 (1–2 meses) · rumo ao 1.0 formal

| # | Item | Tipo | Esf. | Critério de aceite | Origem |
|---|------|------|------|--------------------|--------|
| 3.1 | **CHANGELOG + versionamento de API (`/v1`)** | 🤖 | M | governança de release; rotas sob `/v1`; CHANGELOG mantido | Roadmap P2 #10 |
| 3.2 | **Staging dedicado** | 🔑 | G | Railway env + Supabase branch; migrations validadas antes de prod (maior lacuna citada por todos) | Roadmap P2 #11 · Mapa §4.2 |
| 3.3 | **Jobs assíncronos p/ tarefas fiscais longas** | 🔑 | G | worker/fila no Railway; calculadora/laudo deixam de ser bloqueantes | Roadmap P1 #9 |
| 3.4 | ✅ **TypeScript strict no frontend** (já feito em 2026-06-03, commit 7166a497) | 🤖 | M | `noUnusedLocals/Parameters: true` em ambos tsconfig; `tsc --noEmit` bloqueante no CI | Mapa §2.4 |
| 3.5 | **SLA/SLO + rotação de segredos** | 🔑 | M | metas documentadas + Sentry/logs confirmados em prod; rotação do JWT secret/chaves | Roadmap P2 #12, #13 |

**Saída do Sprint 3:** release governado, staging com rollback, TS strict, SLO/rotação documentados.

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

> **Resumo:** Sprint 1 (P0) entregue e mergeável. Sprint 2–3 têm 3 itens prontos para preparo
> (2.1, 2.2, 2.5) cuja *aplicação* é 🔑, e 3 que exigem **decisão/spec sua** (2.3 catálogo,
> 2.4 risco-prod, 3.1 breaking) antes de irem para produção.

---

## Itens 🔑 (dependem de você — infra/credenciais/decisão)
- **2.1 (parte live):** spec do endpoint da API oficial do portal Tributos.
- **3.2 Staging:** provisionar Railway env + Supabase branch.
- **3.3 Jobs assíncronos:** worker/fila no Railway.
- **3.5 SLA/SLO + rotação:** metas de negócio + acesso a key management.

## Sequência recomendada (modo automático)
`1.1 → 1.2 → 1.3 → 1.4 → 2.1 → 2.2 → 2.5(preparo) → 2.3 → 2.4 → 3.1 → 3.4`

Os itens 🔑 entram conforme você libera infra/credenciais/spec.

## Critério de 1.0 (do roadmap, com status atual)
- [ ] Cobertura: backend ≥ 80% (hoje 74%) · ✅ frontend ≥ 70% — ~78% com gate no CI (2026-06-09).
- [ ] E2E cobrindo conciliação, laudo, auth.
- [ ] CBS/IBS sem SERPRO, apontando calculadora oficial + apuração persistida.
- [ ] Hardening P0 completo (refresh revogável no logout, rate-limit testado, RLS sem drift).
- [ ] Staging + rollback + SLA/SLO documentados.
- [ ] CHANGELOG + versionamento de API.

---

**Gerado:** 2026-06-09, a partir do remapeamento completo. Atualizar ao fim de cada sprint.
