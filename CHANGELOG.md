# Changelog

Todas as mudanças relevantes do OrgConc. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento
[SemVer](https://semver.org/lang/pt-BR/).

> Pré-1.0: a API ainda pode mudar entre versões menores. O critério de 1.0 está
> em [`docs/ROADMAP_1.0.md`](docs/ROADMAP_1.0.md).

## [Não lançado]

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

### Alterado
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
