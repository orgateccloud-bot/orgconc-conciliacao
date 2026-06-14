# Análise do projeto OrgConc — por Claude Fable 5

_Modelo: `claude-fable-5` · gerado por auditoria automatizada multi-passo_


---

# Relatório Executivo Consolidado

# RELATÓRIO EXECUTIVO CONSOLIDADO — Auditoria Técnica OrgConc

**Data-base:** auditorias por subsistema (7 recortes, ~263k tokens de código). **Escopo não coberto:** migrations SQL (`db/rls/`, `supabase/migrations/`), policies RLS reais, comando de deploy do uvicorn (proxy-headers), suíte de testes backend — incertezas marcadas onde relevante.

---

## 1. Visão Geral

O OrgConc é um SaaS de conciliação bancária e auditoria fiscal/forense para escritórios contábeis brasileiros: ingestão OFX/CSV/XML (NF-e/CT-e), conciliação heurística e via LLM (Claude single/multi-modelo com juiz), forense determinística (smurfing, carrossel, risk score), enriquecimento CNPJ (BrasilAPI/RFB), apuração CBS/IBS (LC 214/2025) e geração de laudos XLSX/HTML/PDF.

**Stack:** FastAPI + SQLAlchemy 2 async/asyncpg + Postgres/Supabase com RLS desenhado; React 19/TS/Tailwind same-origin em `/app`; deploy Railway via Docker; CI GitHub Actions com job dedicado de RLS.

**Maturidade — diagnóstico central:** engenharia individual **acima da média** (anti-XXE com defusedxml em todos os parsers, anti-SSRF no WeasyPrint, refresh tokens rotativos hasheados, UPSERT incremental de custo LLM, RLS por transação com `SET LOCAL`, docs operacionais reais), porém com **uma falha sistêmica que anula o restante: o isolamento multi-tenant está desenhado, documentado e desligado**. A conexão de produção roda com BYPASSRLS (admitido na docstring de `rls_context.py`), as queries não filtram `org_id`, e routers/frontend têm múltiplos furos de tenancy independentes. O sistema **não deve custodiar dados de mais de um escritório real** até o P0 abaixo.

---

## 2. Mapa de Arquitetura

```
Browser (SPA /app, Bearer em sessionStorage + refresh httpOnly)
   │ same-origin
FastAPI (bootstrap.criar_app)
   │ middlewares: Prometheus → RequestId → RLSContext(ASGI puro) → CORS → SecurityHeaders → BodyLimit
   ├─ Routers (17): auth multi-org │ conciliação │ fiscal/laudo │ CRUDs │ metrics │ exports
   │     padrão dominante: "fat router" (SessionLocal direto); migração parcial p/ usecase+repo (clientes)
   ├─ Serviços: conciliacao_llm (Claude, retry, juiz) │ laudo_forense (2090 linhas, GLOBAL mutável)
   │            audit (hash chain) │ ai_insights (cache+heurística) │ calculadora CBS/IBS
   ├─ Matchers/Forense: cascata 6 estágios → orquestrador → matchers DB │ forensics pura │ cnpj_enricher (rede inline!)
   └─ DB: ContextVar org → after_begin SET LOCAL app.org_id → policies RLS (inertes: role BYPASSRLS)
         + camada api/domain (VOs, Protocols) — ÓRFÃ, nada a implementa
Fallback "DB indisponível" → persistência JSON local (efêmera no Railway) — decisão única no boot
```

**Fluxos críticos:** (1) upload → parse → cascata/LLM → dataset persistido → export HTML/XLSX/PDF; (2) OFX+XML → cruzamento fiscal → laudo forense; (3) JWT cookie → refresh rotativo → RLS context.

---

## 3. Top 10 Achados Priorizados (impacto × confiança)

| # | Severidade | Subsistema | Arquivo/Função | Achado | Ação |
|---|-----------|------------|----------------|--------|------|
| 1 | **CRÍTICA** | db-domain | `rls_context.py`, `client.py`, `db/metrics.py`, `audit_events.py`, `conciliacoes.py`, `clientes.py` | RLS inerte (conexão `postgres` BYPASSRLS, admitido em docstring) + **todas** as agregações e listagens sem filtro `org_id`; `AuditEvent` e `ReconciliacaoDataset` nem têm coluna `org_id`; `Cliente.cnpj` unique global. Multi-tenancy hoje **não existe na prática**. | Trocar `DATABASE_URL` para role `app_orgconc` NOBYPASSRLS; `org_id` obrigatório em toda query (defesa em profundidade); adicionar `org_id` a `AuditEvent`/`ReconciliacaoDataset`; unique `(org_id, cnpj)`; teste de integração org-A-não-lê-org-B como gate de CI. |
| 2 | **CRÍTICA** | routers | `activity.py`, `conciliacoes_list.py`, `contratos.py`, `guias.py`, `transacoes.py` | Role `"anonymous"` na allowlist de bypass de tenant em 5 endpoints; usuário com `cliente_id=None` (caso padrão de `/auth/usuarios` + `/auth/refresh`) lista **sem filtro** conciliações, contratos, guias e transações. | Remover `anonymous` das allowlists; fail-closed quando `cliente_id is None` e role=`user`; filtrar por `org_id` do JWT, não só `cliente_id`. |
| 3 | **ALTA** | services | `laudo_forense.py:coletar_dados` (`global EMPRESA`) | Estado global mutável lido por `gerar_laudo_workbook`/`gerar_md`/`cabecalho` → laudo do cliente A com CNPJ/razão do cliente B sob concorrência. O `threading.Lock` em `fiscal.py:gerar_laudo` mitiga mas serializa toda geração e é frágil (qualquer caminho futuro sem lock corrompe). | Refatorar: `empresa` como parâmetro explícito em toda a cadeia de geração; remover global e lock. |
| 4 | **ALTA** | frontend ↔ routers | `<a href="/export/html/{id}">` em `ConciliacaoPage`, `RelatoriosPage`, `ClientesPage`; `exports.py` | Links de export não enviam Bearer: ou retornam 401 (feature quebrada) ou `/export/*` é acessível por `report_id` → **IDOR de relatórios financeiros**. `exports.py` também é o único router sem rate limit (PDF/XLSX caros). *Verificar mecanismo de auth de `/export/*` — não fornecido.* | Substituir por `apiFetchBlob`+`baixarBlob` (já existem); no backend, exigir auth + checar `owner_sub`/org no dataset; rate limit em exports. |
| 5 | **ALTA** | frontend | `api.ts:_clientesCache`, `UploadPage` (`orgconc.last_resultado`, `orgconc.historico.v1`) | Caches em memória/sessionStorage/localStorage **não limpos no logout** → usuário da Org B vê relatório, histórico e carteira de clientes da Org A no mesmo browser. | Listener em `orgconc:logout` limpando cache module-level + chaves `orgconc.*`; cache keyed por sub/org. |
| 6 | **ALTA** | services | `audit.py:registrar_audit`, `_buscar_ultimo_hash` | Hash chain frágil: (a) race em inserts concorrentes → dois eventos com mesmo `prev_hash` → cadeia quebra legitimamente; (b) `payload_hash` não inclui `prev_hash`, `actor_sub`, `action`, `ts` → **alterar metadados não quebra a cadeia**. Para produto de auditoria forense, a propriedade anunciada não se sustenta. | Hash sobre evento completo encadeado (`prev_hash` incluso); serializar insert via `pg_advisory_xact_lock`; teste de concorrência. |
| 7 | **ALTA** | routers | `fiscal.py:_separar_arquivos_fiscal`, `matchers.py:_separar_arquivos` | Zip bomb: limite aplicado ao tamanho **comprimido**; `zf.open(member).read()` expande sem teto de bytes descomprimidos ou nº de membros → DoS de worker com ZIP de 1 MB. | Teto por membro e total descomprimido (leitura incremental), máx. de membros, rejeitar ratio > N:1. |
| 8 | **ALTA** | core | `config.verificar_db_disponivel` | Decisão DB vs. JSON tomada **uma vez no boot**: Postgres indisponível por 30 s no deploy → ciclo inteiro em JSON no filesystem efêmero do Railway = **perda silenciosa de dados fiscais** + split-brain. Log em nível `info`. | Em produção: fail-hard se DB indisponível no boot (alinhado ao fail-fast já existente de `_validate_production_env`); fallback JSON só em dev. |
| 9 | **ALTA** | matchers + infra | `documento.py:consultar_por_documento`, `contrapartes.py:consultar_por_alias`; `SCHEMA.md`, `DEPLOY.md` | Matchers consultam `Cliente` globalmente ignorando `cliente_id` recebido (comentário admite) → razão social de carteira alheia vaza na `Disposicao`. Agravante: `SCHEMA.md` instrui policy `USING (true)` e `DEPLOY.md` `auth.role()='authenticated'` sem `org_id` — **quem provisionar ambiente pela doc recria o furo**. | Filtro de tenant nos matchers; reescrever seções RLS das docs apontando para migrations versionadas como única fonte de verdade. |
| 10 | **ALTA** | core/routers | `bootstrap.BodyLimitMiddleware`, `main.py:/metrics`, `rate_limit._get_rate_key` | Trio de endurecimento: (a) body limit bypassável via `Transfer-Encoding: chunked`; (b) `/metrics` Prometheus público; (c) rate limit por `request.client.host` atrás do LB Railway — sem `--proxy-headers` todos anônimos dividem um bucket (DoS no login); com XFF mal configurado, brute-force bypassa o limite. *Comando uvicorn não auditável — verificar.* | Limitar leitura de stream incremental (não só Content-Length); auth/allowlist em `/metrics`; validar `forwarded-allow-ips` no deploy. |

**Menções honrosas (MÉDIA, corrigir no P1):** replay window na rotação de refresh sem reuse-detection da família (`auth_routes.auth_refresh` — `substituido_por` existe e não é usado); prompt injection cru em `conciliacao.py:conciliar_csv`; `metrics.py:trend/distribuicao/heatmap` sem escopo de user; rede inline no request path em `orquestrador.conciliar` (timeouts garantidos com >50 CNPJs frios); race peek→commit em `llm_metrics.persistir_custo_diario_async` (e chamador não identificado); `meses_observados=5` hardcoded em `risco_tributario` (número errado em carta a cliente); corrida de refresh no frontend (`apiRefresh` sem mutex × rotação single-use = logout espúrio).

---

## 4. Postura de Segurança & Multi-tenancy (consolidada)

**O que está bem (e é raro):** fail-fast de env em prod; Swagger off em prod; CSP/COOP/CORP completos; defusedxml em todo parse; anti-SSRF no WeasyPrint (2 lugares); bleach allowlist correta; bcrypt com truncamento documentado; refresh hasheado server-side; PII masking em logs/Sentry/audit; SQL 100% parametrizado; CI com job RLS contra Postgres real e role NOBYPASSRLS — **o teste existe; a produção é que não usa a role testada**.

**O problema é estrutural, não pontual.** A tenancy falha em **quatro camadas independentes**, então não há defesa em profundidade — há ausência de defesa: (1) **DB**: BYPASSRLS + queries sem `org_id` + colunas `org_id` nullable + tabelas sem `org_id`; (2) **routers**: `anonymous` privilegiado, `cliente_id=None` → sem filtro, endpoints fiscais sem `autorizar_cliente` (`apurar_cbs_ibs`, `gerar_laudo`); (3) **serviços/matchers**: global `EMPRESA`, consultas globais de contraparte; (4) **frontend**: caches sobrevivem ao logout; (5) **docs**: instruem policies permissivas. A correção exige varredura coordenada, não patches isolados.

**Modelo de tenancy ambíguo:** o sistema mistura `org_id` (JWT/RLS) e `cliente_id` (filtro de router) sem regra clara de qual autoriza o quê — é a causa-raiz dos achados #2 e do IDOR provável em `conciliacoes_list.buscar` (`autorizar_cliente(user, "None")`). Definir formalmente: org = tenant; cliente = recurso dentro da org; toda query carrega ambos.

**LGPD:** `AuditEvent.payload` e `ReconciliacaoDataset.payload` (extratos completos) sem política de retenção, TTL ou cifra além do default Supabase — mapear antes de cliente real.

---

## 5. Dívida Técnica & Qualidade

- **Testes:** zero specs no frontend (com `src/test/setup.ts` e `axe-helper.ts` prontos — intenção abandonada); nenhum teste fornecido para CRUD/metrics/listener RLS (exatamente o código que falha silenciosamente). **Gate de cobertura em contradição:** CI exige `--cov-fail-under=80`, docs declaram 74% — ou o CI está vermelho agora, ou as docs mentem.
- **Camada de domínio órfã:** `api/domain/repositories.py` define Protocols sem implementação visível; entidades duplicam ORM com campos divergentes. Decidir: completar (com mapeadores) ou remover. O estado intermediário só custa.
- **Migração arquitetural parcial:** fatia `clientes` usa usecase+repo; `contratos`/`guias` fazem SQLAlchemy no handler; commit dentro do CRUD impede unit-of-work (e é o que impede rotação atômica de refresh token).
- **Drift de infra:** 5 caminhos de deploy (`railway.json` ok; `Procfile` roda Alembic no processo web com role sem ownership; `render.yaml` — rota de DR do BACKUP.md! — instala requirements-dev, perde dados em `/data` e não migra). Semgrep/Trivy com `|| true`/`exit-code: 0` = SAST teatral; `trivy-action@master` = supply chain.
- **Higiene Docker:** container root, CMD shell-form (sem graceful shutdown em deploy), healthcheck com porta hardcoded.
- **Caches sem eviction** (`metrics.py:_bundle_cache` etc.), sem TTL/limpeza para tokens expirados e datasets; type hints monetários `float` sobre `Numeric` (`models.py`); sem Alembic como fonte de verdade visível (SCHEMA.md 10 migrations atrasado).

---

## 6. Roadmap Recomendado

### P0 — bloqueante para operar com >1 tenant real (1–2 semanas)
1. **Tenancy de verdade**: role `app_orgconc` NOBYPASSRLS na `DATABASE_URL` de runtime; `org_id` explícito em todas as queries de `db/metrics.py`, `audit_events.py`, `conciliacoes.py`, `clientes.py`; `org_id` em `AuditEvent`/`ReconciliacaoDataset`; unique `(org_id, cnpj)`. Promover o teste RLS do CI a smoke-test pós-deploy.
2. **Routers**: remover `anonymous` das allowlists (5 arquivos); fail-closed para `cliente_id=None`; `autorizar_cliente`/audit em `gerar_laudo`, `apurar_cbs_ibs`; autorização antes do 404 em `conciliacoes_list.buscar`.
3. **Exports**: auth verificada em `/export/*` (checagem de `owner_sub`+org); frontend via `apiFetchBlob`.
4. **Frontend logout**: limpar `_clientesCache` e chaves `orgconc.*` em `orgconc:logout`.
5. **Remover global `EMPRESA`** do laudo forense (parâmetro explícito).
6. **Fail-hard em prod sem DB** (eliminar fallback JSON silencioso); limites anti-zip-bomb; corrigir `SCHEMA.md`/`DEPLOY.md` (policies) e neutralizar `render.yaml`/`Procfile`.

### P1 — 30 dias
7. Hash chain de auditoria: hash sobre evento completo + advisory lock + teste de concorrência.
8. Refresh: rotação atômica (unit-of-work) + reuse-detection revogando a família; mutex de refresh no frontend (`apiRefresh`).
9. Endurecimento HTTP: `/metrics` autenticado, body limit por stream, validar proxy-headers do uvicorn, rate limit em exports.
10. Enriquecimento CNPJ para background job (fila ou pós-processamento assíncrono); corrigir `meses_observados` hardcoded; sanitizar entrada de CSV no prompt LLM (estruturar como o caminho OFX).
11. Resolver gate de cobertura (80 vs 74) e tornar semgrep/Trivy bloqueantes ou removê-los; pinar actions por SHA; `USER` non-root e `exec` no Dockerfile.

### P2 — trimestre
12. Decidir destino da camada de domínio; mover commits para o caller; concluir migração usecase/repo em `contratos`/`guias`.
13. Alembic como fonte de verdade (eliminar drift Supabase↔ORM↔docs); jobs de retenção/limpeza (tokens, caches, datasets) com política LGPD documentada.
14. Suíte de testes: integração RLS/listener `after_begin`, concorrência (audit, laudo, refresh), e primeiros specs de frontend sobre a infra já existente.
15. Type hints `Decimal` + CHECK/Enum em colunas de status; consolidar caminho único de deploy; revisar pool atrás do pgbouncer.

---

**Veredito:** fundação técnica forte e decisões de segurança pontuais exemplares, mas o produto **vende isolamento que hoje não entrega** — e a falha atravessa DB, API, serviços, frontend e documentação. O P0 é pequeno em volume de código e enorme em risco evitado; nada além dele deveria ser priorizado antes de onboarding de escritórios reais.


---

# Auditorias por subsistema


## backend-core

# Auditoria Técnica — Subsistema `backend-core`

---

## 1. Propósito & arquitetura

O subsistema é o "chassi" da API: `api/core/bootstrap.py:criar_app()` monta o FastAPI com a pilha de middlewares (Prometheus → RequestId → RLSContext → CORS → SecurityHeaders → BodyLimit, em ordem de registro; execução real é a inversa), handlers de exceção e lifespan. `config.py` centraliza env vars, flags globais (`DB_DISPONIVEL`, CORS, limites de upload) e o registry mutável de modelos LLM. `llm_metrics.py` + `prometheus_metrics.py` fazem a telemetria de custo Claude (acumulador in-process + UPSERT incremental em `llm_cost_daily` + counters Prometheus). `rate_limit.py` configura slowapi keyed por `sub` do JWT. `observability.py` integra Sentry com scrubbing de PII. `model_registry.py` resolve dinamicamente o modelo mais recente por família via Models API.

Decisão arquitetural relevante e bem documentada: `RLSContextMiddleware` é ASGI puro (não `BaseHTTPMiddleware`) justamente para que o ContextVar de org propague ao endpoint — correto, já que `BaseHTTPMiddleware` roda `call_next` em task filha (sets internos não propagariam para fora, mas sets externos propagam para dentro; a ordem de registro garante isso).

---

## 2. Pontos fortes (concretos)

- **Fail-fast em produção**: `config._validate_production_env()` exige JWT secret ≥ 32 chars, admin hash, API key e `ORGCONC_CORS_ORIGINS` — derruba o boot em vez de subir inseguro. Excelente.
- **Swagger/ReDoc/OpenAPI desabilitados em prod** (`criar_app`): reduz superfície de reconhecimento de endpoints fiscais.
- **Headers de segurança completos** (`SecurityHeadersMiddleware`): CSP com `frame-ancestors 'none'`, COOP, CORP, `X-XSS-Protection: 0` (correto, o header legado é nocivo), `Cache-Control: no-store` em `/auth/` e `/export/`.
- **UPSERT incremental por delta em `llm_metrics.persistir_custo_diario_async`**: o design `delta_para_persistir`/`confirmar_persistido` com `on_conflict_do_update` somando (não substituindo) é a abordagem correta para multi-worker — raciocínio documentado no docstring.
- **Anti-cardinalidade no Prometheus**: `_rota_template()` usa o template da rota e `registrar_llm_prometheus` normaliza model_id para família.
- **Scrubbing de PII no Sentry** (`observability._before_send` reusando `mask_pii`) + `send_default_pii=False`.
- **429 com headers RateLimit corretos** sem o custo do `headers_enabled=True` do slowapi (decisão explicada em comentário — bom).
- **Ping de DB movido do import-time para o lifespan** — corrige um problema real de boot.

---

## 3. Bugs / riscos reais

| # | Local | Problema | Severidade |
|---|-------|----------|------------|
| 1 | `config.verificar_db_disponivel` | **Decisão DB vs. JSON é tomada UMA vez no startup e nunca revisitada.** Se o Postgres estiver indisponível por 30s no deploy, o app inteiro roda o ciclo de vida com persistência JSON local — em Railway (filesystem efêmero) isso é **perda de dados fiscais silenciosa** e split-brain (parte dos dados no DB, parte em JSON). O log é apenas `info`, não `error`. | **ALTA** |
| 2 | `bootstrap.BodyLimitMiddleware.dispatch` | Só inspeciona `Content-Length`. Request com `Transfer-Encoding: chunked` (sem CL) **bypassa o limite por completo** — uvicorn aceita chunked. `ValueError` em CL malformado também passa direto (deveria ser 400). | **ALTA** |
| 3 | `rate_limit._get_rate_key` → `get_remote_address` | Atrás do proxy da Railway, `request.client.host` é o IP do LB **a menos que** uvicorn rode com `--proxy-headers` + `forwarded-allow-ips` (não visível neste código — **incerteza explícita**). Dois cenários ruins: (a) sem proxy-headers, todos os anônimos compartilham um bucket de 120/min (DoS trivial no login); (b) com proxy-headers mal configurado, `X-Forwarded-For` é spoofável e o rate limit de brute-force em `/auth/` é contornável. | **ALTA** (condicional — verificar comando de deploy) |
| 4 | `llm_metrics.persistir_custo_diario_async` | **Race entre peek e commit**: duas corrotinas chamando concorrentemente leem o mesmo delta em `delta_para_persistir()`, ambas fazem UPSERT (DB soma 2×delta) e ambas confirmam — o custo do dia fica **superestimado**. Não há lock cobrindo o ciclo peek→commit→confirm. Além disso, **não está claro quem chama esta função** (nenhum scheduler/hook visível) — se ninguém chama, `llm_cost_daily` nunca é gravada. | **MÉDIA** |
| 5 | `llm_metrics._price_for` | Model_id desconhecido (não contém fable/sonnet) cai no preço de **haiku** (o mais barato) → subestima custo. Inconsistente com `regist

## backend-services

# Auditoria Técnica — Subsistema `backend-services`

---

## 1. Propósito & Arquitetura

O subsistema é a camada de serviços de domínio de um SaaS de conciliação/auditoria fiscal:

- **Conciliação LLM** (`conciliacao_llm.py`): chamadas ao Claude (SDK síncrono Anthropic em thread pool) com retry/backoff, streaming, cache de system prompt, e síntese multi-modelo ("juiz" Sonnet).
- **Laudo forense** (`laudo_forense.py`, 2090 linhas): geração de workbook XLSX de 11–13 abas + MD/HTML/PDF a partir de OFX + enriquecimento RFB/BrasilAPI + XMLs NF-e/CT-e.
- **Insights IA** (`ai_insights.py`): cache híbrido Postgres (TTL 24h) com fallback heurístico.
- **Persistência** (`db_persistence.py`, `fiscal_persistence.py`, `storage.py`): SQLAlchemy async + um caminho legado psycopg2 síncrono.
- **Transversais**: auth JWT (`auth.py`), trilha de auditoria com hash chain (`audit.py`), sanitização HTML (`sanitize.py`), logging JSON com PII masking (`logging_estruturado.py`), apuração CBS/IBS orquestrando calculadora oficial (`calculadora_cbs_ibs.py` + `calculadora_client.py`).

O padrão geral é "DB opcional" (degrada para arquivo/heurística), boundaries defensivos com `except Exception` logado, e separação razoável transporte/mapeamento (calculadora) e serviço/router (audit não comita; caller decide).

---

## 2. Pontos Fortes (concretos)

- **`sanitize.py`**: allowlist bleach bem desenhada; `img src` restrito a `data:` URIs e `a href` a `https`/`mailto` — anti-XSS e anti-SSRF (WeasyPrint) coerentes. O callable `_allow_attrs` centralizando lógica por tag é a abordagem correta.
- **WeasyPrint com `url_fetcher` bloqueante** (`carta_constatacao._block_url_fetcher`, `laudo_forense._block_url_fetcher`) + `asyncio.to_thread` para CPU-bound — anti-SSRF e não bloqueia o loop.
- **`auth.py`**: bcrypt direto (decisão documentada sobre passlib/bcrypt≥5 com truncamento explícito a 72 bytes), fail-hard de `ORGCONC_JWT_SECRET` em produção, refresh opaco hasheado (sha256) com modelo de revogação documentado e honesto sobre a ausência de denylist de access token.
- **`defusedxml`** no parse de XML de upload (`laudo_forense.parse_nfe/parse_cte`) — anti-XXE correto.
- **`conciliacao_llm.chamar_modelo_async`**: retry apenas em casos retriáveis (`_is_retriable`), detecção de truncamento por `stop_reason`, telemetria de custo que não quebra a resposta, timeout de parede configurável.
- **`fiscal_persistence.salvar_documentos_fiscais`**: bulk insert em lotes de 500 com dedup intra-lote e por banco — correto para o limite de parâmetros do Postgres.
- **`logging_estruturado.py`**: request_id por contextvar, PII masking aplicado a `msg` e `extra`, middleware com latência — boa base de observabilidade.
- **`fiscal_notifications._sanitize_header`**: prevenção explícita de SMTP header injection (CR/LF).
- **`storage.read_limited`**: leitura de upload com limite incremental (anti-OOM).
- **Fallbacks honestos**: `_insights_heuristicos`, stub SEFAZ que declara `NOT_IMPLEMENTED` em vez de fingir funcionar.

---

## 3. Bugs / Riscos Reais

### ALTA

1. **`laudo_forense.py` — `EMPRESA` global mutável (estado compartilhado entre requests).**
   `coletar_dados()` faz `global EMPRESA; EMPRESA = construir_empresa(...)` e `gerar_laudo_workbook()`, `gerar_md()`, `gerar_html()`, `cabecalho()`, `_conformidade_lista()` leem o global. Em FastAPI com requisições concorrentes, o laudo do cliente A pode ser gerado com cabeçalho/CNPJ/razão social do cliente B — **vazamento cross-tenant em documento de auditoria**. O comentário "O serviço NÃO faz I/O nem mantém estado" é contradito pelo próprio código. Se a API só usa `montar_dados`/`gerar_laudo_workbook` e popula `EMPRESA` por outro caminho, o risco persiste igual (é o global que é o problema).

2. **`audit.py:registrar_audit` + `_buscar_ultimo_hash` — hash chain frágil por design e por concorrência.**
   - *Concorrência*: dois inserts simultâneos leem o mesmo "último hash" → dois eventos com o mesmo `prev_hash` → `verificar_cadeia` quebra legitimamente. Não há lock/advisory lock/serialização.
   - *Design*: `payload_hash = sha256(payload)` **não inclui** `prev_hash`, `action`, `actor_sub`, `ts`, `resource_id`. Logo, alterar metadados de um evento (quem fez, o quê, quando) **não quebra a cadeia**; e dois eventos com payload idêntico são intercambiáveis. A propriedade anunciada ("provar integridade") só vale para o JSON do payload, não para a trilha. Para um produto de auditoria forense isso é material.
   - *Ordenação*: `order_by(

## backend-routers

# Auditoria Técnica — Subsistema `backend-routers`

---

## 1. Propósito & arquitetura

O subsistema é a superfície HTTP do OrgConc: `api/main.py` monta a app via `criar_app()` (bootstrap não fornecido — middleware/CORS **não auditáveis aqui**), registra 15 routers e serve o SPA React same-origin em `/app`. Os domínios:

- **Auth multi-org** (`auth_routes.py`): JWT em cookie httpOnly + refresh token rotativo persistido, admin de bootstrap via env vars.
- **Conciliação** (`conciliacao.py`): upload OFX/CSV → parse → heurística local ou LLM (Claude, single/multi-modelo com consenso).
- **Fiscal** (`fiscal.py`, 801 linhas): NF-e/CT-e × OFX, conformidade, risco tributário, laudo forense, carta de constatação, apuração CBS/IBS (stub).
- **CRUDs** (`clientes`, `contratos`, `guias`), **listagens** (`conciliacoes_list`, `transacoes`), **observabilidade** (`metrics`, `activity`, `audit` com hash chain), **exports** (HTML/XLSX/PDF).

Há uma migração arquitetural parcial em curso: a fatia `clientes` usa router → usecase → repositório (`CriarClienteUseCase`, `ClienteRepositorySQL`), enquanto `contratos.py` e `guias.py` fazem SQLAlchemy direto no handler. O padrão dominante é "fat router": handler abre `SessionLocal()`, orquestra serviço e serializa dict manualmente.

---

## 2. Pontos fortes

- **Uploads com limite real**: `read_limited(up, MAX_UPLOAD_BYTES)` + soma acumulada vs `MAX_UPLOAD_TOTAL_BYTES` em todos os endpoints de upload (conciliacao, fiscal, matchers).
- **Login com mitigação de timing**: `auth_routes.auth_login` faz um único `verificar_senha` contra hash candidato ou `_DUMMY_HASH` — não vaza existência de e-mail por timing.
- **Refresh tokens server-side**: hash do token persistido, rotação com encadeamento (`substituido_por`), revogação em troca/reset de senha e `logout-all`. O comentário "NUNCA reemitir admin fixo" e a re-derivação de role/org em `/auth/refresh` mostram cuidado com escalonamento.
- **Cookies bem configurados**: httpOnly, `samesite=strict`, refresh com `path="/auth"` (não trafega em toda requisição).
- **CPU-bound fora do event loop**: `asyncio.to_thread` em `parse_lote_xmls`, `ler_ofx`, `cruzar`, `_gerar_xlsx`, WeasyPrint — correto para FastAPI async.
- **Anti-SSRF no PDF**: `exports._block_url_fetcher` bloqueia fetch externo do WeasyPrint.
- **Mascaramento de PII** (`mask_pii`) em audit/activity; payload de auditoria mascarado recursivamente (`audit._mascarar_payload`).
- **Hash chain de auditoria** com verificação de integridade por janela (`verificar_cadeia`) e por evento (`payload_hash_valid`).
- **Sanitização de nomes de arquivo** (`_SAFE_FILENAME_RE`) e mensagens de erro de parse sem leak (`raise HTTPException(400, "Falha ao parsear arquivo")` + `log.exception` interno).
- **Endurecimento de produção**: `health.py` e `/` omitem versão/detalhes de infra quando `_IS_PROD`; `/auth/hash` retorna 404 em prod.
- Correção consciente de vazamento de cache cross-org em `metrics.py:trust_score`/`modelos` (cache keyed por `user.sub`, referenciando bug #89).

---

## 3. Bugs / riscos reais

### ALTA

1. **Role `"anonymous"` tratado como privilegiado em 5 lugares.** Em `activity.py:feed`, `conciliacoes_list.py:listar`, `contratos.py:listar_contratos`, `guias.py:listar_guias`, `transacoes.py:listar_recentes`, o padrão é:
   ```python
   if user.role not in ("admin", "service", "auditor", "anonymous"):
   ```
   Ou seja, `anonymous` **escapa do filtro de tenant** e enxerga dados de todos os clientes. O código de `current_user` não foi fornecido, mas `auth_routes.auth_hash_helper` checa explicitamente `_user.role == "anonymous"` — então a dependency **pode** devolver um usuário anônimo em vez de 401. Se isso ocorre em qualquer ambiente, é leitura cross-tenant não autenticada de feed de auditoria, conciliações, contratos, guias e transações. Mesmo que `current_user` rejeite anônimos em prod, o padrão é uma bomba-relógio.

2. **Usuário sem `cliente_id` vê tudo.** Em `conciliacoes_list.py:listar`, `contratos.py:listar_contratos`, `guias.py:listar_guias`: se `user.role == "user"` e `user.cliente_id` é `None` (caso típico de usuário multi-org criado por `/auth/usuarios`, que tem `org_id` mas não `cliente_id` — vide `/auth/refresh` que seta `cliente_id=None` para usuários do DB), então `cliente_id` fica `None` e a query lista **sem filtro de tenant**. Mesma falha em `transacoes.py:listar_recentes` (`tenant_id=None` → `listar_transacoes_recentes` sem filtro). O modelo de tenancy mistura `org_id` (JWT) e `cliente_id` (filtro), e os routers só filtram pelo segundo. Não vejo nenhum `WHERE org_id = ...` nem set de GUC de RLS na sessão — **se a conexão Postgres usa role que bypassa RLS (comum com service key do Supabase), o isolamento por org é inexistente nesses endpoints.** Preciso ver `SessionLocal`/RLS para confirmar, mas o código dos routers, sozinho, não isola.

3. **`conciliacoes_list.py:buscar` — conciliação sem `cliente_id` é acessível por qualquer usuário + IDOR provável.** `cliente_id` é opcional em `/conciliar/ofx`; quando `None`, `autorizar_cliente(user, str(c.cliente_id))` recebe a string `"None"`. Comportamento de `autorizar_cliente` com isso é desconhecido — se ele só nega quando há mismatch explícito, conciliações órfãs vazam para qualquer autenticado. Além disso, o 404 ocorre **antes** da autorização (oráculo de existência de `report_id`). O dataset tem `owner_sub` (usado em `exports`), mas `buscar` não o verifica.

4. **Zip bomb em `fiscal.py:_separar_arquivos_fiscal` e `matchers.py:_separar_arquivos`.** O limite (`MAX_UPLOAD_TOTAL_BYTES`) é aplicado ao tamanho **comprimido**; `zf.open(member).read()` expande sem limite de bytes descomprimidos nem de número de membros. Um ZIP de 1 MB pode expandir para GBs em memória → DoS do worker. O rate limit (5/min) mitiga pouco.

5. **`/metrics` Prometheus sem autenticação** (`main.py:prometheus_metrics`). Exposto publicamente em prod (same-origin com a API no Railway), vaza paths, latências, contagens, possivelmente labels com dados de negócio. Deveria exigir token ou ficar atrás de allowlist de IP.

### MÉDIA

6. **`metrics.py:trend/distribuicao/heatmap` não recebem `user` e não escopam por org.** Diferente de `dashboard-bundle`/`trust-score` (cache por user), esses três chamam `crud_metrics.*` sem nenhum contexto de tenant. Se `crud_metrics` não filtra internamente (e não há como, sem receber o user), qualquer usuário autenticado vê métricas globais da plataforma. Inconsistente com o próprio comentário do arquivo que diz que dados são "org-scoped (RLS)".

7. **`auth_routes.auth_refresh` — janela de replay na rotação.** Dois requests concorrentes com o mesmo refresh: ambos passam `buscar_ativo_por_hash` antes do `revogar` → duas sessões válidas emitidas. Pior: apresentar um token **já revogado** retorna apenas 401 — não há *reuse detection* que revogue a família inteira (`substituido_por` existe no schema mas não é usado para isso). O docstring afirma anti-replay; a implementação não cumpre o padrão completo (RFC 6819 / rotação com detecção de reuso).

8. **`fiscal.py:apurar_cbs_ibs` sem autorização de tenant.** Não há `autorizar_cliente`; `salvar_apuracao(db, apuracao)` persiste para o cliente que vier no payload `OperacaoFiscalInput` (schema não fornecido). Se o input carrega `cliente_id`/`documento_id`, é escrita cross-tenant. Incerteza: depende do schema — verificar.

9. **`fiscal.py:gerar_laudo` / `laudo_resumo` sem escopo de tenant nem audit.** Qualquer usuário autenticado processa OFX de qualquer CNPJ; não há `autorizar_cliente`, não há `registrar_audit` (ao contrário de `/fiscal/processar`). Para um produto de auditoria fiscal, gerar laudo forense sem trilha é contraditório.

10. **Prompt injection + custo descontrolado em `conciliacao.py:conciliar_csv`.** `extrato_text` e `razao_text` (até `MAX_UPLOAD_BYTES` cada) entram **crus** no prompt do Claude. Conteúdo de CSV controlado pelo usuário pode instruir o modelo a fabricar conclusões no relatório (que vira HTML/PDF "oficial" de conciliação) e infla custo de tokens. O caminho OFX ao menos passa por parser estruturado (`_fmt_csv`).

11. **Estado global mutável `laudo.EMPRESA` + `threading.Lock`** (`fiscal.py:gerar_laudo:_build`). O lock evita a race, mas serializa toda geração de laudo (gargalo sob concorrência) e o design (módulo com global setada por request) é frágil — qualquer caminho de código futuro que esqueça o lock corrompe laudos entre clientes. Deveria ser parâmetro.

12. **`fiscal.py:risco_tributario` — `meses_observados=5` hardcoded** em `estimar_retencoes_nao_recolhidas`. A anualização do risco fica errada para qualquer período real diferente de 5 meses. Para um número que vai em carta ao cliente, é bug de negócio relevante.

13. **`exports.py` sem rate limit** — único router de leitura sem `@limiter.limit`; geração de PDF (WeasyPrint) e XLSX são caras, dá para saturar o thread pool. Também não validei se `rid` é sanitizado em `carregar_dataset` antes de ir ao filesystem (risco de path traversal — **incerto**, código de `storage` não fornecido).

14. **Caches em memória sem eviction e por-processo** (`metrics.py:_bundle_cache/_trust_cache/_modelos_cache`). Entradas expiradas nunca são removidas (crescimento sem bound com muitos users×períodos); `invalidar_cache_metrics` só limpa `_bundle_cache`, deixando trust/modelos stale; em deploy multi-worker o cache e a invalidação não são compartilhados.

15. **`fiscal.py:gerar_carta` — `str(nova_versao.id)` usado em `registrar_audit` após `db.add()` sem `flush()`.** Se `CartaVersao.id` é `server_default` (gen no Postgres), o id é `None` na auditoria. Se é default Python-side (uuid4), ok. **Incerto** — depende de `models.py`.

### BAIXA

16. **`conciliacao.py:conciliar_ofx`** — o `except (ValueError, KeyError, UnicodeDecodeError)` não c

## backend-matchers-forense

# Auditoria Técnica — Subsistema `backend-matchers-forense`

---

## 1. Propósito & arquitetura

O subsistema é o **motor de conciliação e análise forense** do produto. Três pipelines convivem:

1. **Cascata de conciliação (6 estágios)** — `cascata.py:classificar` roteia cada transação OFX por regex/keywords para um método; `orquestrador.py:conciliar` despacha para os matchers (`documento.py`, `nfe.py`, `guia.py`, `contrato.py`, `contrapartes.py`) e produz `Disposicao` por transação, com pós-enriquecimento de CNPJ inline.
2. **Forense determinística** — `forensics.py` (meio de pagamento, valor redondo, smurfing, carrossel, risk score 0–100) orquestrada por `auditoria_forense.py:analisar_auditoria`, mais `regime_fiscal.py:analisar_regime` (múltiplo do teto Simples/MEI).
3. **Integração fiscal** — `xml_fiscal.py` (parser NF-e/CT-e/NFS-e com situação/cancelamento), `cruzamento_fiscal.py:cruzar` (matching N:M doc×pagamento), `conformidade.py` (score por fornecedor) e `tributario.py` (estimativa de risco em R$).

O **enriquecimento de CNPJ** (`cnpj_enricher.py`) é transversal: cache (Postgres `cnpj_cache` ou JSON local) → BrasilAPI → schema `cnpj.*` (RFB local). Acoplamento ao restante do sistema via `api.parsers.ofx._parse_ofx`, `api.parsers.constants`, `api.db.models` e `api.core.config`.

A arquitetura geral é razoável: módulos puros (forensics, regime, cruzamento) separados de módulos com I/O (matchers DB, enricher). Mas há **violação da própria regra declarada**: o docstring de `auditoria_forense.py` diz "enriquecimento pesado deve ser job de background", enquanto `orquestrador.conciliar` faz rede inline por padrão.

---

## 2. Pontos fortes (concretos)

- **`defusedxml` em todos os pontos de parsing de XML não confiável** (`nfe.py`, `xml_fiscal.py`) — proteção XXE/billion-laughs consciente, com comentário citando B314.
- **`xml_fiscal.py` é o módulo mais maduro**: validação de DV mod-11 da chave (`validar_chave_acesso`), tratamento de eventos de cancelamento (`_chave_cancelada_de_evento`, tpEvento 1101xx), mapeamento de cStat, correção documentada do bug clássico do `.lstrip("NFe")` (`_strip_prefixo_chave`).
- **Exclusão de documentos CANCELADA/DENEGADA** da cobertura fiscal em `cruzamento_fiscal.cruzar` e `conformidade.calcular_conformidade_fornecedor` — evita inflar `volume_nf`.
- **SQL parametrizado em todo lugar** (`text()` com bind params, SQLAlchemy `select`) — sem concatenação de SQL.
- **`conformidade._detectar_flags`**: match de sócio com `re.escape` + `\b` + guarda de comprimento ≥4 — anti-falso-positivo pensado e comentado.
- **Matchers de contrato/guia retornam explicitamente AMBIGUO** em vez de escolher arbitrariamente — postura correta para conciliação contábil.
- **`tributario.py` documenta vigência das alíquotas** e usa `Decimal` com `ROUND_HALF_UP` no cálculo final.
- Cascata BrasilAPI→RFB local com cache, retry com backoff e semáforo de concorrência — desenho de resiliência presente, ainda que com problemas de execução (abaixo).

---

## 3. Bugs / riscos reais

### ALTA

1. **`documento.py:consultar_por_documento` e `contrapartes.py:consultar_por_alias` — consulta global sem filtro de tenant.** Ambos recebem `cliente_id` e **ignoram** (o comentário admite: "não multi-tenant ainda"). Um extrato da firma A pode resolver contraparte contra `Cliente` de outra firma, vazando `nome` (razão social de carteira de clientes alheia) na `Disposicao`. Em SaaS multi-tenant isso é vazamento de dados, não só bug funcional. `documento.resolver` tem o mesmo problema (nem recebe tenant).

2. **`orquestrador.py:conciliar` faz rede no request path por padrão** (`enriquecer_cnpj=True` → `_enriquecer_disposicoes`). Com semáforo=2 e `sleep(0.55)` por slot + até 3 tentativas com backoff (1s, 2s) por CNPJ, um extrato com 100 CNPJs não cacheados leva **dezenas de segundos a minutos**, estourando timeouts do Railway/proxy. Contradiz o desenho declarado em `auditoria_forense.py` (enriquecimento = background job).

3.

## backend-db-domain

# Auditoria Técnica — Subsistema `backend-db-domain`

---

## 1. Propósito & Arquitetura

O subsistema fornece a camada de persistência e domínio do SaaS:

- **`api/db/client.py`** — bootstrap do engine async (SQLAlchemy 2.x + asyncpg), com tolerância a `DATABASE_URL` ausente (engine `None`) e dependency `get_db()` para FastAPI.
- **`api/db/models.py`** — ~20 modelos ORM espelhando o schema Supabase: tenancy (`Org`, `Usuario`), núcleo de conciliação (`Cliente`, `Conciliacao`, `Transacao`), trilha de auditoria hash-chained (`AuditEvent`), módulo fiscal (NF-e/CT-e/cruzamentos/carta), apuração CBS/IBS (LC 214/2025), auth (`RefreshToken`) e caches (`CnpjCache`, `LlmCostDaily`, `AiInsightsCache`, `ReconciliacaoDataset`).
- **Módulos CRUD** (`clientes.py`, `usuarios.py`, `refresh_tokens.py`, `conciliacoes.py`, `audit_events.py`) — funções finas sobre `AsyncSession`.
- **`api/db/metrics.py`** — agregações SQL single-query para o dashboard (KPIs, séries temporais, trust score, custo LLM).
- **`api/db/rls_context.py`** — propagação de tenant via `ContextVar` + listener `after_begin` que injeta `SET LOCAL app.org_id` por transação, alimentando policies RLS no Postgres.
- **`api/domain/*`** — camada de domínio pura (frozen dataclasses, value objects com validação de DV CNPJ/CPF, Protocols de repositório), sem dependências de infra.

A arquitetura segue um esboço de Clean/Hexagonal: domínio puro + Protocols + infra DB. Porém — e isto é central — **a camada de domínio parece desconectada**: os módulos CRUD em `api/db/*` operam diretamente sobre os modelos ORM e não implementam os Protocols de `api/domain/repositories.py`. Não vejo no código fornecido nenhuma implementação concreta de `ClienteRepository`, `ConciliacaoRepository` ou `RefreshTokenRepository`. Se elas não existem em outro subsistema, o domínio é hoje arquitetura aspiracional.

---

## 2. Pontos fortes (concretos)

1. **RLS por transação, não por sessão** — `rls_context.py:_set_org_no_begin` usa `after_begin` em vez de um `SET` único no checkout da sessão. Isso cobre corretamente múltiplas transações por request e o `is_local=true` evita vazamento de GUC com pgbouncer transaction-pooling. Design correto e raro de se ver bem feito.
2. **`ContextVar` com tokens de reset** — `set_org_context`/`reset_org_context` devolvem o `Token`, permitindo restauração correta no middleware (sem vazamento entre tasks no event loop).
3. **Refresh tokens server-side bem modelados** — `RefreshToken` com `token_hash` (sha256, nunca plain — documentado em `refresh_tokens.py`), `substituido_por` (cadeia de rotação anti-replay), `revogado_em`, índice parcial em ativos, e preservação de `role`/`cliente_id` para reemissão correta no refresh.
4. **`AuditEvent` hash-chained** — `payload_hash` + `prev_hash` NOT NULL indicam trilha tamper-evident; índices adequados (`ts DESC`, actor+ts, resource).
5. **Métricas em queries únicas** — `metrics.py:agregar_kpis` etc. fazem agregação no banco (sem N+1); `calcular_trust_score` trata explicitamente o estado vazio em vez de fabricar score (comentário honesto no código).
6. **Value objects com validação real** — `value_objects.py:CNPJ/CPF` validam dígitos verificadores; `mascarado()` para logs (consciência de LGPD); `Valor` força `Decimal` com 2 casas.
7. **Defaults com timezone** — `_now()` usa `datetime.now(timezone.utc)` em vez do clássico bug `datetime.utcnow` (naive).
8. **`connect_args={"statement_cache_size": 0}`** — correto para asyncpg atrás de pgbouncer em transaction mode.
9. **`update ... where revogado_em IS NULL`** em `revogar*` — idempotente e à prova de corrida dupla de revogação.
10. **Normalização de email** centralizada em `usuarios.py:_norm_email`, consistente em criar/buscar.

---

## 3. Bugs / Riscos reais

### ALTA

**A1. `metrics.py` — TODAS as agregações ignoram tenant (`org_id`/`cliente_id`)**
`agregar_kpis`, `serie_temporal`, `distribuicao_modo`, `heatmap_diario`, `performance_modelos`, `calcular_trust_score`, `custo_llm_resumo` consultam `Conciliacao`/`LlmCostDaily` globalmente, sem filtro de organização. O próprio código admite (`rls_context.py` docstring) que **a conexão atual é `postgres` com BYPASSRLS**, logo o RLS é hoje inócuo. Resultado: o dashboard de qualquer org exibe dados agregados de **todas** as orgs — vazamento cross-tenant de volumes financeiros, contagens de anomalias e custos. Mesmo quando o RLS for ligado, depender exclusivamente dele sem defesa em profundidade na query é frágil.

**A2. `audit_events.py:listar_eventos` e `conciliacoes.py:listar_conciliacoes` — sem escopo de org**
Mesmo problema: qualquer caller lista eventos de auditoria e conciliações de todos os tenants. `audit_events` nem tem coluna `org_id` no modelo (`AuditEvent`), então **RLS por org é impossível nessa tabela** — eventos de auditoria de uma org são estruturalmente visíveis a outra (a depender do endpoint que chama). Para um produto de *auditoria fiscal*, isto é grave.

**A3. `client.py` — engine `None` silencioso + RLS inerte = sistema "funciona" sem isolamento**
A combinação de: (a) conexão como superuser/owner com BYPASSRLS (admitido na docstring), (b) `org_id` nullable em praticamente todos os modelos, e (c) queries sem filtro explícito, significa que **o multi-tenancy hoje não existe na prática**, apenas no design. Severidade ALTA porque o produto lida com dados bancários e fiscais de terceiros.

**A4. `clientes.py:atualizar_cliente` / `buscar_cliente` / `buscar_por_cnpj` — sem verificação de tenant**
`db.get(Cliente, cliente_id)` retorna qualquer cliente por UUID, de qualquer org. Se algum router passar o ID vindo do path sem checagem (não tenho o código dos routers — incerteza declarada), é IDOR direto. `cnpj` é `unique` global em `Cliente`, o que também é um bug de modelo multi-tenant: duas orgs não podem cadastrar o mesmo CNPJ de cliente (cenário plausível: dois escritórios atendendo a mesma empresa) — e a existência do CNPJ vaza entre tenants via erro de unicidade.

### MÉDIA

**M1. `rls_context.py:_set_org_no_begin` — `Session` síncrona sob async + `connection.execute` no listener**
O listener roda no greenlet da Session sync subjacente; funciona com asyncpg via greenlet bridge, mas é frágil: se o listener disparar fora do contexto greenlet (ex.: uso de `engine.begin()` direto, sem Session), o `SET` não acontece e nenhum erro é levantado. Além disso, **o registro do listener depende do import lateral em `get_db()`** (`import api.db.rls_context`) — qualquer código que crie `SessionLocal()` diretamente sem passar por `get_db` antes do primeiro request pode operar sem o listener registrado. Acoplamento por efeito colateral de import é um foot-gun.

**M2. `metrics.py:custo_llm_resumo` — mistura de fuso/data**
`hoje = _now_utc().date()` usa UTC, mas o negócio é brasileiro (UTC-3). Custos registrados entre 21h e meia-noite locais caem no "dia seguinte", distorcendo `custo_hoje_usd` e o burn rate na percepção do usuário. BAIXA em impacto financeiro, MÉDIA em confiabilidade percebida do dashboard.

**M3. `models.py` — `Mapped[float]` sobre `Numeric(15,2)` em colunas monetárias**
`Transacao.valor`, `GuiaTributo.valor`, `Contrato.valor`, `DocumentoFiscal.valor_total`, etc. são tipados como `float` (asyncpg devolve `Decimal` para `NUMERIC`, então o runtime entrega `Decimal`, mas a anotação mente). Inconsistente com `Conciliacao.usage_cost_usd: Decimal` e com o domínio (`Valor` usa `Decimal`). Risco real: alguém converte para `float` confiando no type hint e introduz erro de arredondamento em valores fiscais.

**M4. `metrics.py:agregar_kpis` — `SUM(valor_total_credito + valor_total_debito)` com NULLs**
Se **uma** das colunas for NULL na linha, `a + b` é NULL e a linha inteira some do volume (o `coalesce` externo só cobre o caso de soma totalmente nula). Correto seria `SUM(COALESCE(credito,0) + COALESCE(debito,0))`. Também: somar crédito + débito onde débito é presumivelmente negativo — "volume_total" pode estar semanticamente errado (saldo líquido, não volume). Não consigo confirmar a convenção de sinal persistida; verificar.

**M5. `usuarios.py:registrar_login` / `atualizar_senha` — aceitam `str | uuid.UUID` mas não validam**
Diferente de `buscar_por_id`, passam o valor cru ao `where(Usuario.id == usuario_id)`. Uma `str` não-UUID gera erro de cast do asyncpg em runtime (500), não um retorno controlado. Inconsistência interna no mesmo módulo.

**M6. `atualizar_cliente` — sem atualização de `atualizado_em` e sem `onupdate`**
`Cliente.atualizado_em` (e `Org`, `Usuario` etc.) só tem `default`; nenhuma coluna tem `onupdate=_now`. `atualizar_cliente` não toca o campo. Timestamps de atualização ficarão eternamente iguais ao de criação — ruim para auditoria.

**M7. `refresh_tokens.py:revogar_todos_do_sub` e `revogar` — `rowcount` com async + commit por função**
Cada função CRUD faz seu próprio `db.commit()`. Em fluxos de rotação (revogar antigo + criar novo), isso significa **duas transações separadas**: se o processo cair entre elas, o usuário fica sem token válido (falha segura, ok) — mas o padrão "commit dentro do CRUD" impede composição transacional (ex.: revogar+criar atomicamente, anti-replay real). Dívida de design com consequência de corrida.

### BAIXA

**B1. `audit_events.py:contar_eventos`** — não aceita os mesmos filtros de `listar_eventos`; paginação no frontend mostrará total inconsistente quando filtrado.

**B2. `metrics.py:listar_transacoes_recentes`** — filtra por `cliente_id` via JOIN, mas `Transacao` já tem coluna `cliente_id` direta; o JOIN é redundante e levemente mais caro. Sem `cliente_id`, retorna transações globais (volta ao tema A1).

**B3. `client.py` — pool agressivo para pgbouncer**: `pool_size=20, max_overflow=40` por processo, somado ao pooler do Supabase, pode estourar `max_connections` com múltiplas réplicas no Railway. Recomenda-se `NullPool` ou pool pequeno quando atrás de pgbouncer transaction mode.

**B4. `entities.py:Transacao.chave_dedupe`** — `memo[:40]` como componente de dedupe: dois lançamentos legítimos idênticos no mesmo dia (ex.: duas tarifas iguais) colidem. Aceitável como heurística, mas deveria estar documentado como tal (falso-positivo de duplicidade é achado de auditoria!).

**B5. `value_objects.py:Valor.__post_init__`** — comentário diz "banker's rounding é padrão", mas `quantize` sem `rounding=` usa o contexto corrente (`ROUND_HALF_EVEN` por default, sim — porém depende do contexto da thread; explicite `rounding=ROUND_HALF_EVEN`).

**B6. `models.py`** — `ReconciliacaoDataset.owner_sub` e `CnpjCache` sem `org_id`: datasets de export e cache de CNPJ não participam do esquema RLS por org. Para `CnpjCache` é defensável (dado público da RFB); para `ReconciliacaoDataset` (contém extratos!) é um furo no modelo de tenancy — mitigado apenas se o router checar `owner_sub`, o que não posso confirmar.

---

## 4. Segurança

**Multi-tenancy / RLS — o ponto crítico.** O design (GUC `app.org_id` + policies + role `app_orgconc` NOBYPASSRLS) é bom, **mas está explicitamente desligado**: a docstring de `rls_context.py` admite conexão como `postgres` com BYPASSRLS. Combinado com queries sem filtro de org (A1–A4), o isolamento entre escritórios contábeis hoje depende exclusivamente de checagens nos routers, que não estão neste subsistema. **Trate como não-isolado até prova em contrário.** Adicionalmente: todas as colunas `org_id` são nullable — linhas órfãs (`org_id IS NULL`) terão comportamento indefinido sob a policy (visíveis a ninguém ou a todos, dependendo da policy `org_isolation.sql`, que não foi fornecida — incerteza declarada).

**`app.superadmin = 'on'`** (`rls_context.py:_set_org_no_begin`): habilitar leitura cross-org via GUC é aceitável, mas a string `'on'` setada incondicionalmente quando o contextvar está `True` exige que a policy `superadmin_read` seja estritamente `FOR SELECT` e que o middleware seja rigoroso ao setar o contextvar. Não posso auditar o middleware (`api/core/bootstrap.py` não fornecido).

**Injeção SQL** — ✅ Nenhum risco identificado: todo SQL é via SQLAlchemy Core/ORM com bind params; os `text("SELECT set_config(...)")` usam parâmetros nomeados corretamente.

**Segredos** — ✅ `load_dotenv(override=False)` com precedência ao ambiente real é correto. ⚠️ Verificar se a `DATABASE_URL` aparece em logs de erro de conexão (não auditável aqui).

**Auth** — ✅ Hash de refresh token (não armazena plain), bcrypt referenciado para senhas, revogação server-side, cadeia de rotação. ⚠️ `buscar_ativo_por_hash` não usa comparação constant-time, mas como compara hash sha256 indexado no banco, timing attack é impraticável — aceitável. ⚠️ Não há limite de refresh tokens ativos por `sub` (acúmulo ilimitado + sem job de limpeza de expirados visível neste subsistema).

**Validação de entrada** — ✅ no domínio (CNPJ/CPF/Valor/Periodo). ❌ na camada DB: `criar_cliente` aceita `cnpj`/`email` sem validação alguma (o VO `CNPJ` existe mas não é usado aqui — sintoma da desconexão domínio↔infra); `Conciliacao.modo` e `Usuario.role` são strings livres sem CHECK constraint ou Enum; `limit`/`offset` em `listar_eventos`/`listar_conciliacoes` sem teto (um caller pode pedir `limit=10**9`).

**LGPD** — `AuditEvent.payload` (JSONB livre) e `ReconciliacaoDataset.payload` (extratos completos) armazenam dados pessoais/financeiros sem indicação de criptografia em repouso além do default do Supabase, e sem política de retenção visível. Para um produto de auditoria fiscal, mapear isso é obrigatório.

---

## 5. Dívida técnica & Manutenibilidade

1. **Domínio órfão** — `api/domain/repositories.py` define Protocols que nada (neste subsistema) implementa; `api/domain/entities.py` duplica `Cliente`/`Conciliacao`/`Transacao` dos modelos ORM com campos divergentes (ex.: `Transacao` de domínio tem `conta`/`nome`/`checknum`; a ORM tem `banco`/`categoria`/`org_id`). Sem mapeadores explícitos, há dois vocabulários para a mesma entidade — fonte garantida de bugs de tradução.
2. **Commit dentro do CRUD** — impede unit-of-work; cada função é uma transação isolada (ver M7). O padrão correto é o caller (router/use case) controlar a transação.
3. **Estado de módulo em `client.py`** — engine criado no import-time, `engine=None` como modo degradado, e registro de listener por import lateral (`get_db`). Difícil de testar e sensível à ordem de import.
4. **`models.py` mistura camadas de evolução** — comentários de PRs/sprints ("PR 5 apenas adiciona a coluna", "Sprint 1", "IC-02") no código; útil como arqueologia, mas indica ausência de migrações versionadas como fonte de verdade (Alembic não aparece; "espelham o schema do Supabase" sugere schema gerido fora do repo — risco de drift ORM↔banco real, não verificável aqui).
5. **Ausência de testes** neste recorte — zero arquivos de teste fornecidos para CRUD/metrics/RLS. O listener `after_begin` em particular exige teste de integração (é exatamente o tipo de código que falha silenciosamente).
6. **`AuditEvent` hash chain sem mecânica visível** — `prev_hash` NOT NULL implica leitura do último evento + insert atômico (serialização). Onde isso é feito e como evita corrida (duas inserções concorrentes com o mesmo `prev_hash`) não está neste subsistema — se não houver lock/constraint, a cadeia quebra sob concorrência. Incerteza declarada, mas é um ponto a inspecionar com prioridade.
7. **Sem TTL/limpeza** para `AiInsightsCache`, `ReconciliacaoDataset`, `RefreshToken` expirados — crescimento ilimitado.

---

## 6. Recomendações priorizadas

### P0 — antes de qualquer cliente real
1. **Ativar o RLS de verdade**: criar/usar role `app_orgconc` NOBYPASSRLS na `DATABASE_URL`, validar policies com testes de integração (org A não lê org B), e definir comportamento para `org_id IS NULL` (backfill + `NOT NULL` progressivo).
2. **Defesa em profundidade nas queries**: adicionar parâmetro `org_id` obrigatório (ou derivado do contexto) em **todas** as funções de `metrics.py`, `conciliacoes.py`, `audit_events.py` e `clientes.py`. Não confiar só na policy.
3. **Adicionar `org_id` a `AuditEvent`** (e a `ReconciliacaoDataset`) — sem isso, RLS por org é impossível nessas tabelas.
4. **Remover `unique=True` global de `Cliente.cnpj`** → unique composto `(org_id, cnpj)`.

### P1 — curto prazo
5. Corrigir `agregar_kpis`: `SUM(COALESCE(credito,0) + COALESCE(debito,0))` e revisar a semântica de "volume" (usar `ABS(debito)` se débito é negativo).
6. Registrar o listener RLS no import de `client.py` (ou em `models.py`), não dentro de `get_db()`; adicionar teste que falha se o `SET LOCAL` não ocorrer.
7. Mover `commit()` para o caller (unit-of-work); tornar rotação de refresh token atômica (revogar antigo + criar novo na mesma transação).
8. Validar UUID em `registrar_login`/`atualizar_senha` (paridade com `buscar_por_id`); impor teto em `limit` (ex.: `min(limit, 100)`).
9. `onupdate=_now` em todas as colunas `atualizado_em`.

### P2 — médio prazo
10. Decidir o destino da camada de domínio: implementar os repositórios concretos sobre `api/db/*` (com mapeadores ORM↔entidade) **ou** removê-la — o estado intermediário atual só adiciona custo.
11. Corrigir type hints monetários para `Decimal` em `models.py`; adicionar CHECK/Enum para `modo`, `role`, `risco_classe`, `status`.
12. Introduzir Alembic como fonte de verdade do schema (eliminar drift com Supabase).
13. Job de limpeza (tokens expirados, caches vencidos) + política de retenção LGPD para `AuditEvent.payload` e `ReconciliacaoDataset`.
14. Revisar pool (`NullPool` ou pool reduzido atrás do pgbouncer); fuso America/Sao_Paulo nas agregações diárias de custo; `contar_eventos` com os mesmos filtros de `listar_eventos`.
15. Auditar (fora deste subsistema) a mecânica de inserção do hash chain de `AuditEvent` sob concorrência.

---

**Veredito honesto**: a fundação técnica é acima da média (RLS por transação, tokens rotacionáveis, domínio com VOs validados, métricas sem N+1), mas o sistema **hoje não entrega isolamento multi-tenant** — está desenhado, documentado e desligado. Para um SaaS que custodia extratos

## frontend-app

# Auditoria Técnica — Subsistema `frontend-app` (orgconc-react)

---## 1. Propósito & Arquitetura

SPA React 19-style + TypeScript (Vite presumido, não fornecido), servida sob `basename="/app"`, que consome a API FastAPI por caminhos relativos (`/auth/*`, `/conciliar/*`, `/fiscal/*`, `/metrics/*` etc.) — ou seja, **pressupõe proxy/rewrite no mesmo origin** (Railway). Stack:

- **Roteamento**: `react-router-dom` com rotas lazy + `ProtectedRoute` (App.tsx).
- **Auth**: access token Bearer em `sessionStorage` + refresh token em cookie httpOnly (`lib/api.ts:apiRefresh`), contexto em `lib/auth.tsx`.
- **Dados**: majoritariamente `fetch` manual via `apiFetch` com retry-on-401; `@tanstack/react-query` instalado mas usado em apenas 2 páginas.
- **UI**: shadcn/Radix + Tailwind v4, Recharts, sonner, design system próprio ("Direção Leve").
- **Domínios**: upload/conciliação OFX-CSV, matchers, fiscal (conformidade, gaps, risco, cartas, laudo forense), dashboard de métricas/trust-score/auditoria, administração de orgs/usuários.

Nota: o prompt diz "sem arquivos de teste", mas existem `src/test/setup.ts` e `src/test/axe-helper.ts` — **infraestrutura de teste pronta, zero specs**. Isso é pior do que ausência total: sinaliza intenção abandonada.

---

## 2. Pontos Fortes

- **Sanitização de Markdown**: `ConciliacaoPage` usa `rehype-sanitize` no `ReactMarkdown` do relatório — correto, dado que `relatorio_md` pode conter dados de extratos (memos controlados por terceiros). Nenhum `dangerouslySetInnerHTML` em todo o código.
- **Refresh token bem desenhado no fluxo**: `apiFetch` tenta `/auth/refresh` uma vez em 401, com guarda `retryOn401=false` na retentativa e exceção para o próprio path de refresh — evita loop. Evento global `orgconc:logout` desacopla API de UI.
- **Regex de `Content-Disposition` correta**: `apiFetchBlob` usa `(?!\*)` para não capturar `filename*=UTF-8''` (RFC 5987) — detalhe que a maioria erra.
- **Acessibilidade acima da média**: `ProgressBar` força `label` obrigatório via tipo (WCAG 4.1.2), `aria-current` em nav, `role="img"` com `aria-label` em gauges/heatmap, `prefers-reduced-motion` respeitado no CSS, `sr-only` em deltas de KPI.
- **Honestidade de UX**: `SecurityRing` distingue "sem dados" de "score 0"; `DashboardPage` esconde KPIs até existir conciliação ("nada de números antes de dados"); `ComplianceBadges` separa certificado/em-andamento/não-aplicável.
- **Detalhe correto de download**: `AuditoriaForensePage.baixarLaudo` revoga o blob URL em `setTimeout` (revogação síncrona pós-`click()` aborta downloads em Chromium) — comentado e correto. *Inconsistente, porém: `baixarBlob` em api.ts revoga síncrono.*
- **`Promise.allSettled` no dashboard**: falha parcial de trust-score/activity não derruba o bundle.
- **CommandPalette** com filtro `adminOnly` por role, navegação por teclado completa e `aria-modal`.

---

## 3. Bugs / Riscos Reais

### ALTA

**A1. Vazamento de dados entre sessões/organizações no mesmo browser** — `api.ts` mantém cache module-level `_clientesCache` (TTL 60s), `UploadPage.iniciar` grava `orgconc.last_resultado` em sessionStorage e `salvarHistoricoLocal` grava `orgconc.historico.v1` em localStorage. **Nenhum deles é limpo em `apiLogout` ou no evento `orgconc:logout`**. Cenário: usuário da Org A desloga, usuário da Org B loga na mesma aba → `ConciliacaoPage` exibe o último resultado da Org A (relatório completo com anomalias e valores), `RelatoriosPage` exibe o histórico local da Org A, e dentro de 60s `listarClientes()` pode servir a carteira de clientes da Org A do cache em memória. Para um produto que vende RLS e isolamento multi-tenant, isso é um furo direto no frontend.

**A2. Links de export sem credencial Bearer** — `ConciliacaoPage`, `RelatoriosPage` e `ClientesPage` renderizam `<a href="/export/html/{report_id}">` (e xlsx/pdf) como links diretos. O browser **não envia o header `Authorization`** em navegação de link. Duas possibilidades, ambas ruins: (a) os endpoints exigem Bearer → todos esses downloads retornam 401 (feature quebrada); (b) os endpoints são públicos por `report_id` → **IDOR/vazamento de relatórios financeiros** para quem souber/adivinhar o ID. *Incerteza explícita: o backend não foi fornecido; é preciso verificar se `/export/*` usa cookie de sessão ou token assinado na URL.* O frontend deveria usar `apiFetchBlob` + `baixarBlob` (que já existem) para todos esses links.

**A3. HTML do backend executado same-origin** — `LaudoPage.gerar` (formato `html`) faz `window.open(URL.createObjectURL(blob))`: blob URLs **herdam o origin da página criadora**. O mesmo vale para `/export/html/...` aberto com `target="_blank"` servido do mesmo domínio. Se o HTML gerado pelo backend incluir memos/nomes de transações sem escape, é **XSS armazenado com acesso ao sessionStorage (= access token)**. O frontend não controla isso, mas amplifica a superfície. Mitigação no front: `sandbox` via iframe, ou ao menos não abrir HTML de laudo no mesmo origin. *Incerteza: depende do escape no backend — verificar.*

### MÉDIA

**M1. Corrida no refresh de token** — `api.ts:apiRefresh` não tem mutex/deduplicação. O dashboard dispara 4-5 requests em paralelo (`DashboardPage.carregarTudo`); se todas tomarem 401, cada uma chama `POST /auth/refresh` concorrentemente. Se o backend rotaciona refresh tokens (single-use, prática comum), a segunda chamada invalida a sessão → logout espúrio. Implementar promise compartilhada (`let refreshing: Promise<string|null> | null`).

**M2. Logout em falha de rede transitória** — `auth.tsx:refresh`: qualquer erro em `fetchMe()` (inclusive `TypeError: Failed to fetch` por rede) com token presente faz `setToken(null)` e desloga. Deveria distinguir 401/403 de erro de rede.

**M3. Itens de navegação mortos/quebrados** — `Sidebar.tsx:go()` inclui `"anomalias"` em `routableIds`, mas **não existe rota `/anomalias` em App.tsx** → o catch-all `*` redireciona para `/dashboard`; clicar em "Anomalias" (que exibe badge com contagem!) leva silenciosamente ao dashboard. Itens `"auditoria"` e `"seguranca"` (COMPLIANCE_ITEMS) não são routable — botões que não fazem nada.

**M4. Refetch desnecessário em toda navegação** — `App.tsx:DashboardLayout` tem `useEffect(..., [location.pathname])` que chama `fetchHealth

## infra-config-docs

# Auditoria Técnica — Subsistema `infra-config-docs`

---

## 1. Propósito & arquitetura

Este subsistema é a **camada de empacotamento, pipeline e operação** do OrgConc:

- **Build/runtime**: `Dockerfile` multi-stage (Node 22 builda o SPA React → Python 3.12-slim serve tudo via FastAPI same-origin em `/app`), `docker-compose.yml` para uso interno, `start.sh` como wrapper de onboarding.
- **Deploy**: `railway.json` (caminho oficial: build Docker + `preDeployCommand: alembic upgrade head` + healthcheck `/health`), com `Procfile` e `render.yaml` como caminhos paralelos/legados.
- **CI/CD**: `ci.yml` (5 jobs: test, rls, security, frontend, e2e) + `synthetic-monitor.yml` (sonda externa a cada 30 min).
- **Dependências**: split `requirements-prod.txt` (pins exatos) / `requirements-dev.txt` / `requirements.txt` (shim).
- **Docs operacionais**: DEPLOY, RUNBOOK, MONITORING, BACKUP, SCHEMA, README, PROJETO_MAPEAMENTO.

A arquitetura de deploy (same-origin `/app`, migrations em pre-deploy com URL de owner separada da role runtime `app_orgconc` NOBYPASSRLS) é coerente e acima da média para o porte do projeto. O problema central do subsistema não é o desenho — é **drift**: existem **5 caminhos de deploy** (railway.json, Procfile, render.yaml, docker-compose, start.sh) e docs que se contradizem entre si e contra o estado declarado do código.

---

## 2. Pontos fortes (concretos)

1. **CI multicamada real**: job `rls` dedicado provando isolamento contra Postgres 16 real com role NOBYPASSRLS (`tests/test_rls_isolation.py`, `test_rls_real_tables.py`) — raro de ver; é o teste de segurança mais valioso do pipeline.
2. **Job `security` abrangente**: pip-audit (bloqueante), bandit `-ll` (bloqueante), grep de chave Anthropic, verificação de `.env` tracked, Trivy, npm audit `--audit-level=high`.
3. **Higiene de segredos no requirements**: comentário explícito em `requirements-dev.txt` sobre por que semgrep fica fora (conflito pyjwt 2.12 vs 2.13 com fix de CVEs) — decisão consciente e documentada.
4. **Dockerfile multi-stage** com cache de manifestos antes do código, alinhamento Python 3.12 CI↔prod documentado, libs WeasyPrint espelhadas no CI (`ci.yml: "Instalar dependencias do sistema"`).
5. **Migrations no deploy corretas no caminho Railway**: `railway.json:preDeployCommand` roda Alembic *antes* do start, com healthcheck e retry policy — evita migration concorrente entre workers (no caminho Railway; ver §3 sobre o Procfile).
6. **`synthetic-monitor.yml`**: sonda externa simples e barata que cobre a lacuna do healthcheck interno (DNS/cert/roteamento).
7. **Pins exatos em `requirements-prod.txt`** e `docker-compose.yml` com `${JWT_SECRET:?...}` fail-fast em vez de fallback fraco.
8. **Docs operacionais existem de verdade** (RUNBOOK com procedimentos por cenário, BACKUP com RTO/RPO, MONITORING com PromQL) — a maioria dos projetos nesse estágio não tem nada disso.

---

## 3. Bugs / riscos reais

### ALTA

**A1 — `SCHEMA.md` (§ Row Level Security) e `DEPLOY.md` (§3 "Políticas de Segurança") documentam policies que anulam o multi-tenancy.**
`SCHEMA.md` instrui `CREATE POLICY "allow_all_clientes" ... USING (true) WITH CHECK (true)` e `DEPLOY.md` instrui `USING (auth.role() = 'authenticated')` — ambas **sem filtro por `org_id`**. Isso contradiz frontalmente o claim do `PROJETO_MAPEAMENTO_COMPLETO.md` ("RLS real por org_id, FORCE RLS, fail-closed"). **Incerteza explícita**: não tenho `db/rls/` nem `supabase/migrations/` no código fornecido, então não sei qual reflete a produção. Se SCHEMA.md reflete o estado real → multi-tenancy quebrada. Se está desatualizado → qualquer pessoa provisionando um ambiente novo seguindo a doc **recria o furo**. Em ambos os cenários é ALTA. `SCHEMA.md` também declara head `010` vs head `020` no README — confirma que a doc está 10 migrations atrasada.

**A2 — `render.yaml` é um caminho de deploy quebrado/perigoso se alguém o usar (e o RUNBOOK §DR manda usar Render como fallback).**
Três defeitos combinados:
- `buildCommand: pip install -r requirements.txt` → `requirements.txt` agora é shim para **requirements-dev** → instala pytest/bandit/ruff em produção e muda a resolução de dependências vs. a imagem Docker testada.
- `disk.mountPath: /data` mas **não define `ORGCONC_DATA_DIR=/data`** → app escreve em `./data` (efêmero), o disco persistente fica vazio, datasets somem a cada deploy.
- Sem `alembic upgrade head` no start nem em pre-deploy → schema drift garantido.
Como o `BACKUP.md` (DR passo 3) aponta Render/Fly como rota de disaster recovery, esse arquivo seria usado exatamente no pior momento.

**A3 — `Procfile` roda `alembic upgrade head` no processo web.**
`Procfile:1` faz `alembic upgrade head && uvicorn ...`. Problemas: (a) se houver >1 instância, migrations rodam concorrentes; (b) roda com `DATABASE_URL` runtime — segundo o mapeamento, a role runtime é `app_orgconc` NOBYPASSRLS *sem ownership*, então `alembic upgrade head` **falha por permissão** (ou pior, meio-aplica). O Railway prioriza `railway.json`, então hoje é dead code — mas é dead code que vira bomba se alguém deployar via Procfile (Heroku-like). Remover ou alinhar.

### MÉDIA

**M1 — `Dockerfile`: container roda como root.** Não há `USER` non-root. Para um SaaS que processa OFX/XML/PDF de terceiros (parsers = superfície de ataque), um RCE no pdfplumber/WeasyPrint dá root no container.

**M2 — `Dockerfile:CMD` em shell-form.** `CMD uvicorn api.main:app ...` → PID 1 é `/bin/sh`; SIGTERM do Railway não propaga ao uvicorn → sem graceful shutdown (requests de conciliação longas morrem no meio do deploy). Usar `exec uvicorn ...` ou entrypoint script. O `railway.json:startCommand` tem o mesmo padrão (`/bin/sh -c "uvicorn..."` — aqui o `sh -c` com comando único geralmente faz exec implícito, mas o CMD do Dockerfile não).

**M3 — `Dockerfile:HEALTHCHECK` com porta hardcoded.** `curl http://localhost:8000/health` ignora `${PORT}`. Railway injeta `PORT` próprio → se ≠8000, o healthcheck Docker reporta unhealthy permanentemente (Railway usa o `healthcheckPath` próprio, então o dano real é em compose/outros orquestradores — mas é um bug latente).

**M4 — `ci.yml:security`: semgrep e Trivy são teatro.** `semgrep ... --error --quiet || true` e Trivy com `exit-code: "0"` → nunca falham o build. O Makefile (`security:`) repete o `|| true` do semgrep. Ou se assume o ruído e bloqueia, ou se remove — do jeito atual dá falsa sensação de SAST ativo (o mapeamento lista "semgrep ✅" no CI/CD, o que é enganoso).

**M5 — `trivy-action@master`**: pin em branch mutável de action de terceiro = risco de supply chain no CI que tem acesso ao código. Pinar por SHA (idealmente todas as actions, mas `@master` é o pior caso).

**M6 — Drift do gate de cobertura.** `ci.yml:test` usa `--cov-fail-under=80`; `PROJETO_MAPEAMENTO` e `README.md` dizem 74% bloqueante e cobertura atual 74%. Se a doc está certa, **o CI está quebrado agora** (74 < 80); se o CI está certo, as docs mentem. Um dos dois precisa de correção imediata.

**M7 — `docker-compose.yml`: segredos JWT inconsistentes.** Compose injeta `JWT_SECRET` (obrigatório) mas `DEPLOY.md` afirma "a app usa **ORGCONC_JWT_SECRET**". Se `api/core/config.py` só lê `ORGCONC_JWT_SECRET` (não tenho o arquivo — incerteza), o compose sobe sem segredo efetivo e ou falha em prod ou cai em comportamento de dev. Além disso `ORGCONC_AUTH_