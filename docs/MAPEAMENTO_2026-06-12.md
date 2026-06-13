# Mapeamento Completo & Plano de Ação — OrgConc

**Data:** 2026-06-12 · **Branch:** `fix/hardening-fable-findings` (estado integrado: hardening + main mergeada)
**Método:** auditoria multi-agente (109 agentes) — 8 mapeadores de subsistema → 9 auditores por dimensão → verificação adversarial de cada achado → síntese.
**Resultado da triagem:** 91 achados únicos → **54 confirmados · 4 incertos · 12 já corrigidos · 21 falsos-positivos** (a verificação adversarial descartou ~36% dos achados brutos).

---

## 1. Sumário executivo

Saúde geral **média (≈6.5/10)**: a infraestrutura de segurança está madura (RLS real em prod, JWT/bcrypt, CI com SAST bloqueante na fila, hardening de container), mas a dívida estrutural se concentra em **três temas**:

1. **Integridade da trilha de auditoria** — hash chain sem lock de concorrência, sem metadados no hash, e `AuditEvent` sem `org_id` (fora do RLS). É o tema com o achado mais grave.
2. **Robustez de integração** — a calculadora CBS/IBS (RTC) derruba a apuração com 500 cru em respostas malformadas/timeout.
3. **Defesa em profundidade multi-tenant + cobertura de testes** — o isolamento hoje depende 100% do RLS (sem filtro `org_id` explícito em matchers/métricas); caminhos críticos (pdf, jobs, concorrência) sem teste.

**Importante:** a maioria dos achados de "vazamento multi-tenant" foi **descartada na verificação** — o RLS fail-closed já cobre. O que resta é dívida defensiva (frágil se o RLS for revertido), não furo ativo.

## 2. Mapa de saúde por subsistema

| Subsistema | Saúde | Resumo |
|---|---|---|
| `api/core/` | 6.5 | Sólido; validação de "produção" duplicada 5×, `config.py`/`llm_metrics.py` fat sem teste |
| `api/db` + `domain` + `infra` | 6.0 | RLS correto; `Cliente.cnpj` unique global; duplicação de mappers `_to_entity` |
| `api/matchers/` | 6.0 | Cascata funcional; sem filtro `org_id` explícito; fat files; extratores CNPJ duplicados |
| Serviços/laudo (`laudo_forense`, `audit`, `job_queue`) | 5.0 | Hash chain frágil; `laudo_forense` 2.1k LOC; bug de anualização MEI |
| Routers/API REST | 7.0 | Bem cobertos; validação fraca de `empresa_cnpj`; god function `/apurar` |
| `api/parsers/` | 6.5 | Pure functions limpas; `pdf.py` sem teste; `classifier` ~33% coberto |
| Frontend (React 19) | 7.0 | Cache module-level sem invalidação automática; fat components |
| Infra/DevOps | 7.0 | Maduro; gaps de CI/container já endereçados nos PRs #133/#134 |

## 3. Achados confirmados priorizados (top)

| # | Sev. | Subsistema | Achado | Evidência | Esforço |
|---|---|---|---|---|---|
| 1 | **CRÍTICA** | Auditoria | Hash chain sem lock → race entre workers bifurca a cadeia | `api/services/audit.py:43-47` | M |
| 2 | ALTA | Auditoria | Hash não inclui metadados (`action`/`actor`/`ts`) → tamper sem quebrar cadeia | `api/services/audit.py:37-40,120-134` | M |
| 3 | ALTA | Auditoria/RLS | `AuditEvent` sem `org_id` + fora do RLS → trilha global entre orgs | `api/db/models.py:112-130`; `db/rls/org_isolation.sql` | M |
| 4 | ALTA | Auditoria | `_buscar_ultimo_hash()` sem `org_id` → `prev_hash` cruza cadeias entre orgs | `api/services/audit.py:43-47` | M |
| 5 | ALTA | CBS/IBS | `_num()` sem try/except → resposta RTC inválida derruba apuração | `api/services/calculadora_cbs_ibs.py:122-126` | P |
| 6 | ALTA | Calculadora RTC | `chamar_calculadora()` não captura HTTP error/JSON ruim → 500 cru em prod | `api/services/calculadora_client.py:55-56` | P |
| 7 | ALTA | Regime fiscal | Anualização MEI usa meses da empresa, não do MEI → MEIs misclassificados | `api/services/laudo_forense.py:803,920` | M |
| 8 | ALTA | Esquema | `Cliente.cnpj` unique **global** (não `(org_id,cnpj)`) → bloqueia mesmo CNPJ em orgs distintas | `api/db/models.py:45` | M |
| 9 | ALTA | Auth | Access token sem denylist por `jti` → ~120min de validade pós-logout | `api/services/auth.py:12-17,165-173` | M |
| 10 | ALTA | LGPD | `ReconciliacaoDataset` sem TTL/retenção → extratos persistem indefinidamente | `api/services/storage.py:146-173` | M |
| 11 | ALTA | LGPD/Cripto | `payload` JSONB plaintext, sem cifra at-rest (pgcrypto carregado, não usado) | `api/db/models.py:177` | M |
| 12 | ALTA | Integridade | `disposicao`/`status` sem CHECK/Enum → lixo no banco propaga ao laudo | `api/db/models.py:260,332` | M |
| 13 | ALTA | Rate-limit | In-memory + `--workers 2` sem Redis obrigatório → bypass Nx do limite | `api/core/rate_limit.py:36-52`; `railway.json:9` | M |
| 14 | ALTA | Rate-limit | `--forwarded-allow-ips '*'` → XFF forjado burla rate-limit por IP | `Dockerfile:65` | P |
| 16 | ALTA | CNPJ enricher | Enriquecimento BrasilAPI inline no path HTTP, sem circuit breaker | `api/matchers/orquestrador.py:185,210-212` | M |
| 20 | ALTA | Qualidade | `_parse_pdf` sem testes (omitido no `.coveragerc`) | `api/parsers/pdf.py:14-137` | M |
| 21 | ALTA | Tipos $ | `Mapped[float]` em 16+ campos monetários | `api/db/models.py:71-72,302-306` | M |

> Lista completa (54 confirmados + 4 incertos, incluindo ~18 MÉDIA e ~5 BAIXA) no plano em ondas abaixo e no JSON do run.

## 4. Plano em ondas

### Onda P0 — Crítico / bloqueante (dias)
- **P0.1 — Hash chain atômico (#1, #4):** `SELECT … FOR UPDATE` em `_buscar_ultimo_hash()` (filtrando `org_id` quando #3 entregar). *Pronto:* teste de concorrência (`asyncio.gather` de N writes em DB real) prova cadeia íntegra.
- **P0.2 — Robustez RTC (#5, #6):** `_num()` com try/except→0.0+log; `chamar_calculadora()` captura HTTP/JSON error → erro de domínio. *Pronto:* payload corrompido/timeout/500 retornam erro controlado.
- **P0.3 — Rate-limit confiável (#13, #14):** exigir `REDIS_URL` em prod (falha de startup se ausente); restringir `--forwarded-allow-ips` ao range do proxy Railway. *Pronto:* startup aborta sem Redis em prod e XFF forjado não zera o contador.

> P0.3/4 do scorecard (container non-root, SAST bloqueante) **já estão nos PRs #133/#134** — não duplicar.

### Onda P1 — Semanas
- **P1.1 — `org_id` em `AuditEvent` (#3)** + incluir em `org_isolation.sql` + backfill. *Pronto:* org A não lê eventos de org B (teste RLS).
- **P1.2 — Metadados no hash (#2):** hashear JSON canônico `{action,resource,actor,ts,payload,prev_hash}`. *Pronto:* tamper de `action` quebra `verificar_cadeia()`.
- **P1.3 — `org_id` explícito em matchers (#15) + escape ILIKE `%`/`_` (#28).** *Pronto:* teste de isolamento com 2 orgs em DB real.
- **P1.4 — Unique `(org_id, cnpj)` (#8)** e `report_id` (#31). *Pronto:* mesma CNPJ em 2 orgs insere sem erro.
- **P1.5 — Denylist de access token por `jti` (#9)** (Redis TTL=exp). *Pronto:* token revogado falha pós-logout.
- **P1.6 — Auth atômico (#22, #24, #25):** `FOR UPDATE` na rotação; revalidar admin-env; limite de sessões por `sub`.
- **P1.7 — Enum/CHECK em status (#12) + `Decimal` em campos monetários (#21).**
- **P1.8 — Enriquecimento fora do path crítico (#16):** circuit breaker + fallback, ou mover p/ `job_queue`.
- **P1.9 — Cobertura (#20, #27, #39, #40):** `test_pdf_parser.py`; concorrência de jobs; matchers multi-tenant.
- **P1.10 — Validar `empresa_cnpj` (#29) + teto em `offset` (#36).**

### Onda P2 — Trimestre
- **P2.1 — Retenção/TTL LGPD (#10)** + job de limpeza.
- **P2.2 — Cripto at-rest (#11)** no `payload` (pgcrypto/Fernet).
- **P2.3 — Heurísticas forenses (#7, #32, #33, #34):** anualização per-MEI; smurfing só em débitos; auto-movimentação por similaridade; revisar `+1` em meses.
- **P2.4 — `org_id` em `AiInsightsCache` (#30) + flush de custo LLM no SIGTERM (#35).**
- **P2.5 — Baseline de migrations `000_bootstrap` (#38)** validado em CI (DB vazio → head).
- **P2.6 — Refatorar fat files:** `laudo_forense.py` (2.1k), `cnpj_enricher.py` (476), `forensics.py` (411); React Query no SPA.

## 5. Itens descartados na verificação (registro)

**Falsos-positivos** (RLS/controle existente já cobre): métricas sem `org_id` (RLS fail-closed); race no logout (JS single-thread + `finally` síncrono); Content-Disposition/`rid` (regex `[a-f0-9]{12}`); `LoginPayload` sem min_length (anti-enumeração intencional); path traversal em ZIP (nomes descartados); pool pgbouncer (`statement_cache_size=0`); `TokenPayload` claims extras (Pydantic ignora); CSRF (SameSite+CSP+CORS); ranges `^`/`~` no package.json (lockfile + `npm ci`); cache pip do CI (design correto).

**Já corrigidos** (nesta leva de PRs): container non-root (#133), SAST bloqueante (#134), oráculo 404 vs 403, exports autenticados (#136), reuse-detection de refresh.

---
_Gerado por auditoria multi-agente em 2026-06-12. Os números de achado (#) referenciam a tabela priorizada; lista bruta completa no run `wf_95c352eb`._
