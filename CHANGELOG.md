# Changelog

Todas as mudanças relevantes do OrgConc. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento
[SemVer](https://semver.org/lang/pt-BR/).

> Pré-1.0: a API ainda pode mudar entre versões menores. O critério de 1.0 está
> em [`docs/ROADMAP_1.0.md`](docs/ROADMAP_1.0.md).

## [Não lançado]

### Adicionado (3ª rodada 2026-06-10)
- **Fila de jobs assíncronos (P1 #9, #122)**: `POST /fiscal/laudo/async` →
  `job_id`; polling `GET /jobs/{id}`; download `GET /jobs/{id}/resultado`.
  Fila em Postgres (migration 023, RLS + policy `worker_access`) com worker
  asyncio embutido nas réplicas (claim `FOR UPDATE SKIP LOCKED`, retry de
  órfãos, TTL). Núcleo do laudo compartilhado (`laudo_async`) — síncrono e
  assíncrono geram o mesmo documento. Validado no staging ponta-a-ponta.
- **UI do laudo via fila (#124)**: LaudoPage/AuditoriaForense geram pelo
  `gerarLaudoComFila` (fases na UI + fallback síncrono em 503/403).
- **Observabilidade do banco (#123)**: ping de DB loga o erro real por
  tentativa + error final; monitor sintético ganhou a sonda "Runtime com
  banco" (`POST /auth/refresh` sem cookie: 401 ok / 503 alarme).
- **Pipeline CBS/IBS validado AO VIVO contra a Calculadora oficial (#127)**:
  a API do Portal RTC é ABERTA (sem credencial) — `apurar_via_calculadora`
  reproduziu o gabarito do Manual RTC na produção oficial (NCM 8425.31.10,
  cClassTrib 200031: CBS R$ 36,00 + IBS-UF R$ 4,00, base V0033, memória
  citando o Art. 132 da LC 214/2025); 9/9 verificações no
  `scripts/validar_calculadora_live.py`. Ajustes do contrato real:
  `dhFatoGerador` (substitui o deprecated `dataHoraEmissao`) e pre-flight de
  versão no caminho oficial `/calculadora/dados-abertos/versao`. Para volume
  em produção, a RFB recomenda o componente OFFLINE self-hosted (mesmo motor;
  `CALCULADORA_BASE_URL` aponta para ele sem mudança de código).
- **Auth sob `/v1` (#126)**: dual-mount completo; frontend usa `/v1/auth/*`
  — exceto `refresh`/`logout`, que leem o cookie httpOnly (path `/auth`) e
  ficam na raiz por design.

### Alterado (3ª rodada 2026-06-10)
- **SLO vigente**: as 5 metas de `docs/SLO.md` foram aprovadas pelo owner
  (P2 #12 concluído) — disponibilidade ≥99,5%, 5xx <1%, p95 leitura <800ms,
  p95 fiscal síncrono <60s, RPO≤24h/RTO≤4h.

### Segurança (3ª rodada 2026-06-10)
- **Rotação de segredos executada** (runbook P2 #13): `ORGCONC_JWT_SECRET` e
  `ORGCONC_AUTH_TOKEN` rotacionados em produção (2026-06-10, sem downtime —
  refresh tokens são opacos e independem do JWT secret); senha do role
  `app_orgconc` rotacionada na correção do incidente. Pendentes (somente
  owner): `ANTHROPIC_API_KEY` (console Anthropic) e `ORGCONC_ADMIN_SENHA_HASH`.

### Corrigido (3ª rodada 2026-06-10)
- **Incidente: produção rodou ~32h sem banco no runtime** (senha do
  `app_orgconc` divergente na `DATABASE_URL` — rotação parcial; o preDeploy
  seguia passando pelo `ALEMBIC_DATABASE_URL`, mascarando). Corrigido com
  reset da senha via owner + variável + redeploy; prevenções no #123. Ver
  `docs/postmortems/2026-06-10-prod-sem-db-senha-app-orgconc.md` e RUNBOOK §5.

### Adicionado
- Cobertura de testes do frontend para 17/17 páginas + componentes
  (CommandPalette, AIInsightsPanel, AuditEventModal) e cliente `api.ts` (#104),
  aprofundada para **~88% linhas** (345 testes) com **gate de cobertura no CI**
  em 86 (#109).
- Cobertura de testes do **backend** elevada a **80%** (704 testes; 6 módulos de
  lógica pura a 100%) com gate `--cov-fail-under` 74 → **80** no CI (#110).
- Headers `X-RateLimit-Limit/Remaining/Reset` + `Retry-After` nas respostas 429,
  via handler dedicado; testes de throttle no CI (#104).
- Testes de `logout`/`logout-all`/idempotência e documentação do modelo de
  revogação de sessão (#104).
- Remapeamento técnico, planejamento de execução e relatório executivo (#104).

### Adicionado (2ª rodada 2026-06-09)
- **E2E profundo com backend real** (#114): upload OFX→resultado→export,
  auditoria forense (resumo + laudo XLSX) e erros de negócio; `preview.proxy`
  no vite destravou E2E sem mock (24/24 estáveis).
- **Staging dedicado** no Railway (env `staging` + Postgres próprio +
  `web-staging`) — migrations validáveis fora de prod (`docs/STAGING.md`).
- `docs/SLO.md` (metas propostas) e `docs/ROTACAO_SEGREDOS.md` (runbook).
- Refactor do laudo: fase de cálculo pura `preparar_calculo_laudo` (#115) com
  prova ao centavo nos dados reais; laudo agora 100% determinístico (aba 7
  ordenava por iteração de set). **Fase 2** (#118): agregados das abas
  (transf. internas, classes de risco, fluxos, MEIs × teto, tributário,
  pós-baixa) extraídos para funções puras da fase de cálculo — render só
  renderiza; nova prova ao centavo (0 divergências em 262.939 células).
  **Fase 3** (#120): risk score por transação anexado às disposições na fase
  pura (`_anexar_risco_disps`); abas 5/6 só leem (elimina o cálculo 2× por
  transação); mesma prova ao centavo.

### Corrigido (2ª rodada 2026-06-09)
- **Laudo (MD/HTML/PDF): "Volume anualizado projetado" mostrava o anualizado do
  último MEI** (ex.: R$ 1.467,59) em vez do da empresa (R$ 192,9M no caso real)
  — variável sombreada pelo loop da aba 9; regressão do `59401c1e` reintroduzida
  na reconciliação #59. XLSX nunca foi afetado; múltiplo sempre correto (#116).
- Migrations 021/022 aplicadas em produção (#107): policies RLS legadas
  removidas + idempotência da apuração CBS/IBS (verificado no banco vivo).

### Alterado
- **API versionada sob `/v1` (dual-mount)**: rotas de negócio respondem em
  `/v1/*` e na raiz (retrocompat do frontend). Fora do `/v1`: auth/sessão
  (cookie de refresh com path `/auth`), `/metrics` e `/app`. OpenAPI documenta
  só o caminho canônico. **Frontend migrado p/ `/v1`** (#119): `lib/api.ts`
  usa o caminho canônico em todas as rotas de negócio; `/auth` segue na raiz
  (cookie de refresh com path fixo — migração coordenada futura).
- **CBS/IBS sem SERPRO**: removida a auth OAuth2/Consumer-Key e as vars
  `SERPRO_*`; `serpro_client.py` → `calculadora_client.py` (transporte aberto p/
  a calculadora oficial `consumo.tributos.gov.br` / offline). Em prod
  `CALCULADORA_MODO=stub` o runtime não muda (#106).

### Corrigido
- Documentação desatualizada: README citava UI legada `static/` inexistente;
  comentário de GitHub Pages removido em `api/main.py` (#104).

## [0.5.0] — 2026-06 — beta avançado em produção

### Adicionado
- **Multi-tenancy real**: RLS por `org_id` (FORCE RLS, fail-closed), usuários
  multi-org, login por usuário+org no token, superadmin cross-org read-only,
  `ALEMBIC_DATABASE_URL` (owner) separado do runtime `app_orgconc` (#73–#84).
- **Admin**: página de gestão de usuários e organizações (#85).
- **Dashboard** redesenhado: empty-first honesto, bento, a11y, command palette
  ⌘K, Insights da IA desacoplados, cache por tenant (#87–#94).
- **Login** na identidade ORGATEC; troca/reset de senha com revogação de refresh
  (#77, #95).
- **CBS/IBS**: scaffold + Fase 1 (mapeamento regime-geral) + pre-flight de versão
  da base; persistência em `apuracao_cbs_ibs` (#70–#72).
- **Laudo forense**: pipeline (cascata 6 estágios), laudo XLSX/MD/HTML/PDF
  (WeasyPrint), carta de constatação.
- Observabilidade: Prometheus `/metrics`, Sentry, logging JSON, rate-limit
  (Redis-ready via `REDIS_URL`).

### Alterado
- Stack: **Tailwind CSS 4** (CSS-first, sem `tailwind.config.js`) (#100);
  **bcrypt 5** com `passlib` removido (#99); GitHub Actions atualizadas (#96).
- TypeScript **strict** no frontend (`noUnusedLocals/Parameters`), `tsc --noEmit`
  bloqueante no CI.

### Removido
- GitHub Pages (frontend agora same-origin servido pela API em `/app`).
- Dados/caminhos sigilosos (LOCAR) hardcoded e scripts one-off (#61–#62).

### Segurança
- PDF via WeasyPrint (Playwright proibido no `api/` — corrige 500 em prod)
  (#66–#67).
- RLS re-auditado live (fail-closed provado); deploy com migrations em
  `preDeployCommand` usando role de owner separada.

[Não lançado]: https://github.com/orgateccloud-bot/orgconc-conciliacao/compare/main...HEAD
