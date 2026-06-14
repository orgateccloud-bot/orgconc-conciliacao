# Estado do Projeto OrgConc — 2026-06-11

_Mapeamento pós-implementação da 2ª rodada de hardening (branch `fix/hardening-fable-findings`).
Substitui a leitura de risco do `ANALISE_FABLE.md` (auditoria de 2026-06, hoje parcialmente desatualizada)._

---

## 1. Visão geral

SaaS de conciliação bancária e auditoria fiscal/forense para escritórios contábeis:
ingestão OFX/CSV/XML (NF-e/CT-e), conciliação heurística e via LLM (Claude
single/multi-modelo com juiz), forense determinística (smurfing, carrossel, risk
score), enriquecimento CNPJ (BrasilAPI/RFB), apuração CBS/IBS (LC 214/2025) e
laudos XLSX (11–13 abas) / HTML / PDF.

**Stack:** FastAPI + SQLAlchemy 2 async/asyncpg + Supabase Postgres com RLS real;
React 19 + TS + Tailwind 4 same-origin em `/app`; deploy Railway via Docker;
CI GitHub Actions (test, rls, security, frontend, e2e).

**Qualidade:** cobertura backend 80% (gate 80) · frontend ~88% (gate 80) —
critério 1.0 cumprido. 715 testes backend + 347 frontend verdes.

---

## 2. Correção central vs. ANALISE_FABLE.md

A auditoria Fable apontou como falha sistêmica "RLS desenhado, documentado e
desligado". **Isso não reflete mais a produção:**

- **RLS real por `org_id` ATIVO e enforçado desde 2026-06-07** — backend conecta
  como `app_orgconc` (NOBYPASSRLS), 11 tabelas de negócio com FORCE RLS + policy
  `org_isolation` fail-closed (sem `app.org_id` → zero linhas). Re-auditado live
  em 2026-06-08.
- A auditoria leu docstrings/READMEs defasados — que **agora foram corrigidos**
  para não induzir o mesmo erro de novo (ver §4, item docs).

## 3. Status do Top-10 da auditoria (achado → estado)

| # | Achado | Estado |
|---|--------|--------|
| 1 | RLS inerte + queries sem org_id | **Resolvido em prod** (rollout 2026-06-07). Defesa em profundidade nas queries de `db/metrics.py` permanece P1 |
| 2 | `anonymous` em allowlists + `cliente_id=None` fail-open | **Corrigido nesta rodada** — `escopo_cliente_listagem()` central; anonymous negado em prod nos 5 routers |
| 3 | Global `EMPRESA` no laudo | **Corrigido** (commit `7cc5faf2` — contextvars, sem lock) |
| 4 | Exports sem auth / IDOR | **Já estava correto** no backend (`current_user` + `verify_sub` + rate-limit). Links `<a href>` do frontend seguem como melhoria P2 (UX, não furo: backend nega sem Bearer) |
| 5 | Caches não limpos no logout | **Corrigido** (commit `a362af48` — `limparDadosTenant()` + teste) |
| 6 | Hash chain frágil (metadados fora do hash, sem lock) | **Pendente P1** — exige mudança de formato + migração da cadeia existente |
| 7 | Zip bomb | **Corrigido** (commit `a362af48` — teto descomprimido por membro/total + `test_zip_seguro.py`) |
| 8 | Fallback JSON silencioso sem DB | **Mitigado** — endpoints dependentes de DB retornam 503; monitor sintético cobre. Fail-hard de boot em prod segue P2 |
| 9 | Matchers sem filtro de tenant + docs com policies permissivas | **Docs corrigidas nesta rodada** (SCHEMA/DEPLOY/db-rls README). Matchers: o RLS por org já filtra no banco; filtro explícito na query segue P1 |
| 10 | Body limit chunked + `/metrics` público + rate-limit atrás do LB | **Corrigido nesta rodada** (411 sem Content-Length; `/metrics` fechado em prod com token p/ scraper; `--proxy-headers` no uvicorn) |

## 4. Implementado nesta rodada (commit `3c14dde9`)

**Tenancy/routers**
- `escopo_cliente_listagem()` em `api/services/auth.py` — ponto único do filtro
  de tenant em listagens; remove o padrão `role not in (..., "anonymous")`
  duplicado em 5 routers; anonymous negado em produção.
- `GET /conciliacoes/{report_id}`: não-autorizado responde **404 anti-oráculo**
  (não revela existência do report_id).

**Auth**
- **Reuse-detection de refresh token (RFC 6819):** refresh já rotacionado
  reapresentado >10s após a revogação ⇒ revoga todas as sessões do usuário +
  `audit_event auth.refresh_reuse_detected`. Reapresentação <10s (corrida
  benigna de tabs) ⇒ 401 simples. +2 testes.
- Frontend: **mutex em `apiRefresh`** (N requests com 401 simultâneo compartilham
  uma única chamada — pré-requisito do single-use); `auth.tsx` só desloga em
  401/403 real (falha de rede transitória preserva a sessão).

**HTTP/infra**
- `/metrics` Prometheus: fechado em produção; `ORGCONC_METRICS_TOKEN` habilita
  scraping autenticado (`Authorization: Bearer`).
- `BodyLimitMiddleware`: `411 Length Required` para POST/PUT/PATCH sem
  Content-Length (fecha o bypass por `Transfer-Encoding: chunked`); `400` para
  Content-Length malformado.
- uvicorn com `--proxy-headers --forwarded-allow-ips '*'` (railway.json +
  Dockerfile) — rate-limit e logs enxergam o IP real atrás do LB Railway;
  `CMD exec` (uvicorn vira PID 1 → graceful shutdown no deploy).

**Fiscal/LLM**
- `/fiscal/risco-tributario`: anualização sobre o **período real** dos extratos
  (`_meses_observados`), não mais 5 meses hardcoded — número que vai em carta a
  cliente.
- `/fiscal/laudo`: trilha de auditoria (`fiscal.laudo.gerar`) — era o único
  artefato sensível sem audit.
- `conciliar_csv`: conteúdo dos arquivos delimitado com `<dados_extrato>` /
  `<dados_razao>` + diretiva anti prompt-injection.

**Docs (achado: provisionar pela doc recriava o furo)**
- `SCHEMA.md` / `DEPLOY.md`: seções RLS reescritas — `db/rls/` é a fonte de
  verdade; removido SQL permissivo copy-paste (`USING (true)`,
  `auth.role()='authenticated'`).
- `db/rls/README.md` + docstring de `rls_context.py`: estado real (ATIVO em
  prod) em vez de "não ativado".

**UI**
- Sidebar: item "Anomalias" apontava para rota inexistente (caía silenciosamente
  no dashboard) → alias para `/conciliacao`.

## 5. Pendências priorizadas

### P1 (próximas semanas)
1. **Hash chain de auditoria**: incluir `prev_hash`/`actor`/`action`/`ts` no hash
   + `pg_advisory_xact_lock` na inserção + teste de concorrência (exige migração
   da cadeia existente — planejar formato versionado).
2. **Defesa em profundidade nas agregações**: `org_id` explícito em
   `db/metrics.py` (`agregar_kpis`, `serie_temporal`, `trend/distribuicao/heatmap`
   do router) — hoje dependem só do RLS.
3. **Filtro de tenant nos matchers** (`documento.py:consultar_por_documento`,
   `contrapartes.py:consultar_por_alias`) — RLS cobre em prod, mas a query deve
   filtrar também.
4. **Rate-limiter e custo-LLM in-memory** → multi-instância degrada (não quebra);
   mover para Postgres/Redis quando escalar réplicas.
5. CI: tornar semgrep/Trivy bloqueantes ou removê-los; pinar actions por SHA;
   `USER` non-root no Dockerfile.

### P2 (trimestre)
6. Exports do frontend via `apiFetchBlob` (links `<a href>` hoje dão 401 limpo).
7. Fail-hard de boot em prod sem DB (eliminar fallback JSON de vez);
   neutralizar `render.yaml`/`Procfile` (caminhos de deploy paralelos).
8. Camada de domínio órfã: completar repositórios ou remover; commits para o
   caller (unit-of-work).
9. Retenção/TTL LGPD para `AuditEvent.payload` e `ReconciliacaoDataset`;
   limpeza de refresh tokens expirados.
10. Remover código SERPRO restante do roadmap CBS/IBS (alvo: API portal
    Tributos — `consumo.tributos.gov.br`).

## 6. Branches e PRs em aberto

| Item | Estado |
|------|--------|
| `fix/hardening-fable-findings` | 3 commits (zip-bomb/logout/rate-limit · EMPRESA contextvars · esta rodada) — pronto para PR |
| PR #129 (plano remodelagem docs) | aguardando OK do owner |
| PR #130 (remodelagem relatórios Fases 0-2) | CI verde, aguardando OK do owner |
| Worktrees `rls-rollout`, `jobs-assincronos` | ativos; 3 worktrees `C:/OrgConc/*` prunable |

---

_Gerado por Claude (Fable 5) em 2026-06-11, após verificação achado-a-achado
contra o código atual e implementação dos itens confirmados._
