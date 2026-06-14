<!-- Gerado por mapeamento multi-agente em 2026-06-12. Top-3 achados (hash chain, _num, cnpj unique) spot-checked no código. -->

# Plano de Ação — Hardening e Multi-Tenant OrgConc
*Branch `fix/hardening-fable-findings` · Data: 2026-06-12*
*Origem: mapeamento multi-agente (109 agentes · 8 subsistemas mapeados · 91 achados → verificação adversarial)*

## 1. Sumário executivo

A saúde geral do sistema é **média (6/10)**: a infraestrutura de segurança (RLS real em prod, JWT/bcrypt, CI com SAST, container hardening) está madura, mas há **dívida estrutural concentrada em três temas dominantes**: (a) **isolamento multi-tenant defensivo** (código depende 100% de RLS, sem filtro explícito de `org_id` em matchers, métricas e auditoria); (b) **integridade da trilha de auditoria** (hash chain sem lock, sem metadados, sem `org_id`); e (c) **robustez de integração e cobertura de testes** (calculadora RTC sem tratamento de erro, PDF/jobs/RLS sem testes). Dos **54 achados confirmados** (de 91 brutos; 21 falso-positivos e 12 já corrigidos descartados na verificação adversarial), contabilizam-se aproximadamente **2 CRÍTICOS, 15 ALTOS, 18 MÉDIOS e 5 BAIXOS** (após ajuste de severidade), além de **~30 descartados** (falso-positivo ou já corrigido — em sua maioria reclassificações de "matchers sem org_id" que o RLS já mitiga). O subsistema mais frágil é o **núcleo de serviços/laudo (5/10)** pela concentração de LOC e do hash chain; o mais saudável é a **infraestrutura/DevOps (7/10)**.

## 2. Mapa de saúde por subsistema

| Subsistema | Saúde | Resumo |
|---|---|---|
| `api/core/` (bootstrap, config, RLS mid., métricas, rate-limit) | 6.5 | Sólido, mas validação de "produção" duplicada 5x e config/llm_metrics são fat files sem teste. |
| `api/db` + `api/domain` + `api/infra/repositories` | 6.0 | RLS correto; `Cliente.cnpj` unique global e duplicação de pattern de query/mapeamento. |
| `api/matchers` (cascata 6 estágios) | 6.0 | Funcional; sem filtro `org_id` explícito, duplicação de extratores CNPJ/helpers XML, fat files. |
| Núcleo serviços/laudo (`laudo_forense`, `audit`, `job_queue`) | 5.0 | Hash chain frágil; `laudo_forense` 2000+ LOC; bugs de anualização MEI. |
| API REST (routers `fiscal`/`auth`/`conciliacao`) | 7.0 | Endpoints bem cobertos; validação fraca de `empresa_cnpj`; god function `/apurar`. |
| `api/parsers` (OFX/PDF/XML) | 6.5 | Pure functions limpas; `pdf.py` sem testes; duplicação em `anomalies`/`classifier`. |
| `orgconc-react/src` (SPA React 19) | 7.0 | Cache manual module-level sem invalidação automática; fat components; sem React Query. |
| Infra/DevOps (Docker, CI, RLS, migrations) | 7.0 | Maduro; Trivy não-bloqueante, actions não pinadas, container root pendente de merge. |

## 3. Achados confirmados priorizados

| # | Sev. | Subsistema | Achado | Evidência | Esforço |
|---|---|---|---|---|---|
| 1 | CRÍTICA | Auditoria | Hash chain sem lock → race entre réplicas bifurca a cadeia | `api/services/audit.py:43-47` | M |
| 2 | ALTA | Auditoria | Hash chain não inclui metadados (`action`, `actor_*`, `ts`) → tamper sem quebrar cadeia | `api/services/audit.py:37-40,120-134` | M |
| 3 | ALTA | Auditoria/RLS | `AuditEvent` sem `org_id` + fora da policy RLS → trilha global, vaza ações entre orgs | `api/db/models.py:112-130`; `db/rls/org_isolation.sql:39-46` | M |
| 4 | ALTA | Auditoria | `_buscar_ultimo_hash()` sem filtro `org_id` → `prev_hash` global cruza cadeias entre orgs | `api/services/audit.py:43-47` | M |
| 5 | ALTA | CBS/IBS | `_num()` sem try/except → resposta RTC inválida derruba apuração | `api/services/calculadora_cbs_ibs.py:122-126` | P |
| 6 | ALTA | Calculadora RTC | `chamar_calculadora()` não captura `HTTPStatusError`/JSON malformado → 500 em prod | `api/services/calculadora_client.py:55-56` | P |
| 7 | ALTA | Regime fiscal | Anualização de MEI usa `meses_obs` da empresa, não do MEI → MEIs misclassificados | `api/services/laudo_forense.py:803,920` | M |
| 8 | ALTA | Esquema | `Cliente.cnpj` unique **global** (não `(org_id,cnpj)`) → bloqueia mesmo CNPJ em orgs distintas | `api/db/models.py:45` | M |
| 9 | ALTA | Auth | Access token sem denylist por `jti` → janela de ~120min de validade pós-logout | `api/services/auth.py:12-17,165-173` | M |
| 10 | ALTA | LGPD | `ReconciliacaoDataset` sem TTL/retenção → extratos sensíveis persistem indefinidamente | `api/services/storage.py:146-173`; `migrations/.../011_*` | M |
| 11 | ALTA | LGPD/Cripto | `payload` JSONB plaintext, sem cifra at-rest (pgcrypto carregado, não usado) | `api/db/models.py:177`; `api/services/storage.py:109-112` | M |
| 12 | ALTA | Integridade | `disposicao`/`status` sem CHECK/Enum → lixo no banco propaga a laudos | `api/db/models.py:260,332` | M |
| 13 | ALTA | Rate-limit | In-memory sem Redis + `--workers 2` → bypass de Nx do limite | `api/core/rate_limit.py:36-52`; `railway.json:9` | M |
| 14 | ALTA | Rate-limit | `X-Forwarded-For` aceito de qualquer IP (`--forwarded-allow-ips '*'`) → bypass de rate-limit por IP | `Dockerfile:65`; `api/core/rate_limit.py:33` | P |
| 15 | ALTA | Matchers | `documento.py`/`contrapartes.py` sem filtro `org_id` explícito (mitigado por RLS, frágil) | `api/matchers/documento.py:108-110`; `contrapartes.py:47` | P |
| 16 | ALTA | CNPJ enricher | Enriquecimento BrasilAPI inline no path HTTP, sem timeout de resposta nem circuit breaker | `api/matchers/orquestrador.py:185,210-212` | M |
| 17 | ALTA | Infra | Dockerfile roda como root (UID 0) → RCE em parser escala a root (fix em branch não mergeada) | `Dockerfile:14,65` | P |
| 18 | ALTA | CI/CD | Trivy `exit-code: "0"` → HIGH/CRITICAL não bloqueiam merge | `.github/workflows/ci.yml:158` | P |
| 19 | ALTA | CI/CD | `aquasecurity/trivy-action@master` não pinada a SHA → risco supply chain | `.github/workflows/ci.yml:153` | P |
| 20 | ALTA | Qualidade | `_parse_pdf` sem testes unitários (omitido em `.coveragerc`) | `api/parsers/pdf.py:14-137`; `.coveragerc:4` | M |
| 21 | ALTA | Tipos $ | `Mapped[float]` em 16+ campos monetários (BD ok, agregações em memória derivam) | `api/db/models.py:71-72,101,302-306,479-488` | M |
| 22 | MÉDIA | Auth | Refresh token rotation sem lock atômico → 2 tokens válidos por ~20s | `api/db/refresh_tokens.py:62-99`; `api/routers/auth_routes.py:212-262` | P |
| 23 | MÉDIA | Auth | `escopo_cliente_listagem()` permite user multi-org cherry-pick `cliente_id` | `api/services/auth.py:273-277` | P |
| 24 | MÉDIA | Auth | Admin por env desativado mantém superadmin via refresh se `ORGCONC_ADMIN_EMAIL` igual | `api/routers/auth_routes.py:241-249` | M |
| 25 | MÉDIA | Auth | Sem limite de sessões ativas por `sub` (DoS de sessões) | `api/db/refresh_tokens.py:16-39` | M |
| 26 | MÉDIA | Rate-limit | `verify_exp=False` na key → token expirado consome quota do user legítimo (DoS) | `api/core/rate_limit.py:21-26` | P |
| 27 | MÉDIA | Jobs | `worker_loop` engole exceção genérica → execução duplicada de job órfão sem healthcheck | `api/services/job_queue.py:217-241` | M |
| 28 | MÉDIA | Matchers | ILIKE com wildcards `%`/`_` não escapados → matching incorreto de contrapartes | `api/matchers/contrapartes.py:27-47` | P |
| 29 | MÉDIA | Routers | `empresa_cnpj` sem validação em `/fiscal/laudo`,`/async`,`/resumo` → injeção HTML em metadados de laudo | `api/routers/fiscal.py:326,441` | P |
| 30 | MÉDIA | Cache/IA | `AiInsightsCache` sem `org_id` (chave só `actor_sub`) → risco de vazamento de insights | `api/db/models.py:133-146`; `api/services/ai_insights.py:73-82` | P |
| 31 | MÉDIA | Esquema | `Conciliacao.report_id` unique global (atenuado: hash UUID) | `api/db/models.py:67`; `api/db/conciliacoes.py:26-28` | M |
| 32 | MÉDIA | Forensics | Smurfing acumula `abs(valor)` sem filtrar débito → falso-positivo em receitas | `api/matchers/forensics.py:117,121-129` | P |
| 33 | MÉDIA | Conformidade | Auto-movimentação por substring de razão social (20 chars) → remove fluxos legítimos | `api/services/laudo_forense.py:645` | P |
| 34 | MÉDIA | Regime fiscal | `_meses_observados` adiciona `+1` dia → infla anualização ~1-3% | `api/matchers/auditoria_forense.py:59` | P |
| 35 | MÉDIA | Custo LLM | Acumulador in-memory sem flush no SIGTERM → perda de custo do dia em rolling deploy | `api/core/llm_metrics.py:151`; `api/core/bootstrap.py:185-212` | P |
| 36 | MÉDIA | Routers | Sem limite superior em `offset` → table scans caros (DoS) | `api/routers/audit.py:65`; `api/routers/conciliacoes_list.py:42` | P |
| 37 | MÉDIA | Routers/Jobs | Sem hard-limit de jobs enfileirados por org → enqueue em massa de laudos | `api/routers/fiscal.py:323,380`; `api/services/job_queue.py:94-119` | M |
| 38 | MÉDIA | DB/Migrations | `001_baseline.py` é marker vazio → bootstrap em env novo não-reproduzível | `migrations/versions/001_baseline.py:21-25` | P |
| 39 | MÉDIA | Testes | Jobs (claim/timeout/retry) sem teste de concorrência com DB real | `api/services/job_queue.py:94-184`; `tests/test_jobs_queue.py` | M |
| 40 | MÉDIA | Testes | Matchers sem teste de isolamento multi-tenant com DB real | `tests/test_matchers_documento.py:40-46` | M |
| 41 | BAIXA | Auth | `nbf` validado por PyJWT mas sem teste/doc → risco de regressão futura | `api/services/auth.py:166-168` | P |
| 42 | BAIXA | Auth | Timing attack no login mitigado por dummy hash, mas sem teste de timing | `api/routers/auth_routes.py:38,147-156` | M |
| 43 | BAIXA | CBS/IBS | `_round2` com `+1e-9` inócuo e inconsistente com `tributario.py` | `api/services/calculadora_cbs_ibs.py:52-53` | P |
| 44 | BAIXA | Qualidade | Testes com mock sem `assert_called_with` → podem passar vacuamente | `tests/test_matchers_documento.py:176-200`; `tests/test_metrics.py:332-352` | P |
| 45 | INCERTO | Auth | Reuse-detection de refresh sem teste de concorrência real (confirmar se emite 2 tokens) | `api/db/refresh_tokens.py:42-52`; `api/db/client.py:41` | M |

## 4. Plano em ondas

### Onda P0 — Crítico / bloqueante (dias)
Objetivo: fechar a janela de corrupção de auditoria, crashes de produção e bypass de controles ativos.

- **P0.1 — Hash chain atômico (#1, #4)**: usar `SELECT ... FOR UPDATE` em `_buscar_ultimo_hash()` (filtrando por `org_id` quando a coluna existir — depende de #3). **Pronto quando:** teste de concorrência (`asyncio.gather` de N writes em DB real) prova cadeia íntegra e `verificar_cadeia()` passa.
- **P0.2 — Robustez RTC (#5, #6)**: `_num()` com try/except → 0.0 + log; `chamar_calculadora()` captura `HTTPStatusError`/`ValueError` → erro de domínio tratado. **Pronto quando:** testes com payload corrompido/timeout/HTTP 500 retornam erro controlado, não 500 cru.
- **P0.3 — Container non-root (#17)**: cherry-pick de `chore/dockerfile-nonroot` (5bd169fb) → `USER appuser`. **Pronto quando:** imagem roda como UID≠0 e a suíte de 734+ testes passa no CI.
- **P0.4 — CI bloqueante (#18, #19)**: Trivy `exit-code: "1"` + `ignore-unfixed: true`; pinar `trivy-action` a SHA (re-aplicar b19ea345). **Pronto quando:** CI falha em CRITICAL injetado e a action está pinada.
- **P0.5 — Rate-limit confiável (#13, #14)**: exigir `REDIS_URL` quando `ORGCONC_ENV=prod` (falha de startup se ausente); restringir `--forwarded-allow-ips` ao range do proxy Railway. **Pronto quando:** startup aborta sem Redis em prod e XFF forjado não zera o contador (teste).

### Onda P1 — Semanas
Objetivo: completar isolamento multi-tenant (defesa em profundidade) e integridade da auditoria; cobrir caminhos sem teste.

- **P1.1 — `org_id` em `AuditEvent` (#3)**: adicionar coluna + FK, incluir em `org_isolation.sql`, repassar `org_id` em `registrar_audit()`, backfill NULL para antigos. **Pronto quando:** policy RLS ativa em `audit_events` e teste prova org A não lê eventos de org B.
- **P1.2 — Metadados no hash (#2)**: hashear JSON canônico de `{action, resource_type, resource_id, actor_*, ts, payload, prev_hash}`. **Pronto quando:** tampering de `action` quebra `verificar_cadeia()`.
- **P1.3 — Filtro `org_id` explícito nos matchers (#15, #28)**: `.where(Cliente.org_id == ...)` em `documento.py`/`contrapartes.py` + escape de `%`/`_` no ILIKE. **Pronto quando:** teste de isolamento com 2 orgs em DB real (#40) passa.
- **P1.4 — Unique composto `(org_id, cnpj)` (#8, #31)**: migrar `Cliente.cnpj` e `Conciliacao.report_id` para constraint com `org_id`. **Pronto quando:** mesma CNPJ em 2 orgs insere sem `IntegrityError`.
- **P1.5 — Denylist de access token (#9)**: Redis `revoked:{jti}` com TTL=exp + check em `decodificar_token()`. **Pronto quando:** access token revogado falha imediatamente pós-logout (teste).
- **P1.6 — Auth atômico (#22, #24, #25, #45)**: `FOR UPDATE` na rotação de refresh; revalidar admin-env ativo no refresh; limite de N sessões por `sub`. **Pronto quando:** teste de concorrência rejeita ≥1 dos 2 requests simultâneos.
- **P1.7 — Enum/CHECK em status (#12)** e **tipos `Decimal` (#21)**: StrEnum + CHECK Postgres; converter campos monetários + mypy gate. **Pronto quando:** insert de status inválido é rejeitado e somas em memória usam Decimal.
- **P1.8 — Enriquecimento fora do path crítico (#16)**: circuit breaker + fallback silencioso, ou mover para `job_queue`. **Pronto quando:** BrasilAPI offline não trava o request de conciliação.
- **P1.9 — Cobertura de testes (#20, #27, #39, #40)**: `test_pdf_parser.py`; testes de concorrência de jobs; healthcheck de worker; matchers multi-tenant. **Pronto quando:** novos testes passam e gate de cobertura mantém-se ≥80%.
- **P1.10 — Validação de `empresa_cnpj` (#29) + `offset` (#36)**: `pattern`/validador 400 nos 3 endpoints fiscais; `le=10000` em offsets. **Pronto quando:** entrada malformada retorna 400.

### Onda P2 — Trimestre
Objetivo: LGPD, correções de heurística forense, refatorações estruturais e robustez operacional.

- **P2.1 — Retenção/TTL LGPD (#10)**: coluna `expira_em` + job de limpeza assíncrono. **Pronto quando:** datasets > política são removidos automaticamente.
- **P2.2 — Cripto at-rest (#11)**: pgcrypto ou Fernet application-level no `payload` + rotação de chave. **Pronto quando:** dump do BD não expõe extratos em plaintext.
- **P2.3 — Correções de heurística (#7, #32, #33, #34)**: anualização per-MEI; smurfing só sobre débitos; auto-movimentação por similaridade (Jaro-Winkler) + word-boundary; reavaliar `+1` em meses. **Pronto quando:** testes com cenários divergentes batem o laudo-verdade.
- **P2.4 — `AiInsightsCache` + custo LLM por org (#30, #35)**: `org_id` na chave de cache; flush de acumulador no shutdown + `org_id` no custo. **Pronto quando:** insights e custo isolados por tenant e sem perda no rolling deploy.
- **P2.5 — Baseline de migrations (#38)**: `000_bootstrap` com DDL completo, validado em CI (DB vazio → `alembic upgrade head`). **Pronto quando:** novo env sobe sem SQL manual prévio.
- **P2.6 — Refatorações estruturais**: decompor `laudo_forense.py` (2000+ LOC), `cnpj_enricher.py` (476), `forensics.py` (411); centralizar extratores CNPJ e helpers XML duplicados; React Query no SPA. **Pronto quando:** módulos abaixo de ~400 LOC e duplicações eliminadas, sem regressão de testes.
- **P2.7 — Limpeza de baixo risco (#41, #42, #43, #44)**: testes de `nbf`/timing; simplificar `_round2`; `assert_called_with` nos mocks; remover 3 policies legadas `*_org_policy`. **Pronto quando:** testes adicionados e lint/mock-assertions verdes.

## 5. Itens descartados (registro)

- **Matchers sem filtro de tenant (documento/contrapartes)** — *já corrigido*: RLS ativo (app_orgconc NOBYPASSRLS, FORCE RLS, `after_begin` SET LOCAL); permanece como dívida defensiva, tratada em P1.3.
- **Métricas/KPIs sem `org_id` (agregar_kpis, etc.)** — *falso-positivo*: isolamento via RLS fail-closed no banco, não em SQL de aplicação.
- **Rate-limiter in-memory entre réplicas** — *já corrigido (contexto)*: hoje 1 instância × 2 workers compartilham processo; risco real só ao escalar réplicas (coberto em P0.5).
- **Pool pgbouncer transaction mode / prepared statements** — *já corrigido*: `statement_cache_size=0` em client/env/conftest.
- **Oráculo 404 vs 403 em `report_id`** — *já corrigido*: ambos retornam 404 idêntico.
- **CSRF/Clickjacking sem token CSRF** — *já corrigido*: SameSite=strict + CSP form-action/frame-ancestors + X-Frame-Options DENY + CORS whitelist.
- **semgrep não-bloqueante** — *já corrigido então revertido por merge*: re-aplicar fix de b19ea345 (incluído em P0.4).
- **`env.py` carrega `.env` sem validação** — *já corrigido*: falha visível no preDeploy + monitor sintético (#123); `override=False` é intencional.
- **`Org.cnpj` unique global** — *falso-positivo*: Org = tenant raiz; unicidade global defensável no modelo de negócio.
- **`LlmCostDaily.dia` unique global / sem tenant** — *falso-positivo*: tabela de infra, isolamento por RBAC (`require_role`) por design.
- **`TokenPayload` aceita claims extras** — *falso-positivo*: Pydantic v2 ignora extras; autorização usa só campos tipados; forjar exige o JWT secret.
- **RefreshToken sem `org_id`** — *falso-positivo*: `sub` é UUID único por user×org; org re-derivada do DB na rotação (incerto rebaixado a defesa em profundidade opcional).
- **Claims do JWT sem validação de origem** — *falso-positivo*: `org_id` garantido por FK; RLS fail-closed filtra org fraudulento.
- **Acumulador LLM sem eviction / memory leak** — *falso-positivo*: 6 escalares O(1), reseta diariamente.
- **Peek-commit LLM sem atomicidade na virada do dia** — *falso-positivo*: DB commitado antes do flag; coberto por `test_confirmar_persistido_dia_diferente`.
- **Consulta RFB local sem tenant scoping** — *falso-positivo*: dados RFB são públicos; cache global apropriado.
- **Path traversal em ZIP** — *falso-positivo*: nomes de membros sempre descartados/sanitizados antes de qualquer IO.
- **`report_id` / Content-Disposition sem validação** — *falso-positivo*: `_RID_RX` `fullmatch([a-f0-9]{12})` antes do uso.
- **`LoginPayload` sem min_length de senha** — *falso-positivo*: omissão intencional anti-enumeração; força enforçada na criação.
- **Race no logout (cache frontend)** — *falso-positivo*: JS single-threaded + `finally` síncrono + RLS no backend.
- **Classifier sem teste** — *falso-positivo*: 5 testes existem (gap de cobertura ~33%, não ausência).
- **package.json / CI cache pip ranges** — *falso-positivo*: risco mitigado por lockfile/controles existentes; design de cache correto.
- **`test_smoke_export_pdf` só happy path** — *falso-positivo*: cobre UTF-8/tabelas; falta apenas stress (não crítico).

---
Arquivos-fonte de referência citados acima (caminhos absolutos): `D:\01_Projetos_Ativos\OrgConc\api\services\audit.py`, `D:\01_Projetos_Ativos\OrgConc\api\services\calculadora_cbs_ibs.py`, `D:\01_Projetos_Ativos\OrgConc\api\services\laudo_forense.py`, `D:\01_Projetos_Ativos\OrgConc\api\db\models.py`, `D:\01_Projetos_Ativos\OrgConc\api\core\rate_limit.py`, `D:\01_Projetos_Ativos\OrgConc\api\matchers\documento.py`, `D:\01_Projetos_Ativos\OrgConc\api\matchers\contrapartes.py`, `D:\01_Projetos_Ativos\OrgConc\Dockerfile`, `D:\01_Projetos_Ativos\OrgConc\.github\workflows\ci.yml`.