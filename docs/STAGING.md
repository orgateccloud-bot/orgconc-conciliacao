# Staging — Railway (P2 #11)

> Criado em 2026-06-09 via Railway CLI. Fecha a maior lacuna apontada pelas
> avaliações: **migrations e mudanças passam a ser validáveis fora de produção**.

## Topologia

| Recurso | Valor |
|---|---|
| Projeto Railway | `blissful-empathy` |
| Environment | `staging` (produção: `production` — intocada) |
| Serviço app | `web-staging` (deploy via CLI `railway up`) |
| Banco | Postgres do Railway (serviço `Postgres` no env staging — **isolado de prod/Supabase**) |
| URL | https://web-staging-staging-7aff.up.railway.app |
| Healthcheck | `GET /health` (mesmo `railway.json` do repo) |

## Variáveis (env staging — NUNCA copiadas de produção)

`ORGCONC_ENV=staging` · `ORGCONC_JWT_SECRET` (gerado, exclusivo) ·
`ORGCONC_AUTH_TOKEN` (token de serviço exclusivo) · `ANTHROPIC_API_KEY=sk-ant-test`
(sem custo LLM) · `ORGCONC_MODELS_AUTO=0` · `ORGCONC_CORS_ORIGINS=<URL acima>` ·
`DATABASE_URL` e `ALEMBIC_DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (referência
ao Postgres do staging — migrations rodam no banco de staging no preDeploy).

> Os valores ficam só no Railway (dashboard → web-staging → Variables).
> Se precisar, rotacione-os por lá — staging não compartilha nada com prod.

## Fluxo de uso

1. **Validar uma branch antes do merge** (manual, do checkout da branch):
   ```bash
   railway link --project blissful-empathy --environment staging --service web-staging
   railway up --detach     # build Docker + preDeploy (alembic upgrade head no Postgres de staging) + healthcheck
   curl https://web-staging-staging-7aff.up.railway.app/health
   ```
   Se a migration quebrar, quebra AQUI — produção intocada.
2. **Smoke autenticado**: `Authorization: Bearer <ORGCONC_AUTH_TOKEN do staging>`.
3. (Opcional, dashboard) Conectar o serviço `web-staging` ao repo GitHub com
   branch `staging` para auto-deploy por push — hoje o deploy é via CLI.

## Bootstrap do banco (feito em 2026-06-09) — e um ACHADO

O 1º deploy falhou no `alembic upgrade head`: **a cadeia de migrations não é
bootstrapável em banco vazio** (`relation "conciliacoes" does not exist`) — o
schema base de produção nasceu fora do Alembic (mesma causa do incidente de CI
#64). Já validou o propósito do staging no primeiro uso.

Bootstrap aplicado (uma vez): `Base.metadata.create_all` (ORM, 20 tabelas) +
`alembic stamp head` → daqui em diante o preDeploy valida normalmente cada
migration NOVA contra o Postgres de staging. Follow-up opcional: migration
000_bootstrap p/ tornar a cadeia auto-suficiente.

Verificado: `GET /health` → `{"status":"ok","banco_dados":"ok"}` ·
`alembic_version=022` · 20 tabelas.

## Custo & limpeza

Serviço + Postgres pequenos (créditos do plano). Para desligar tudo:
`railway environment delete staging` (remove serviços e banco do env).

## O que o staging NÃO é

- Não tem RLS/Supabase real (o Postgres é do Railway; o rollout RLS usa role
  `app_orgconc` + policies — replicável via `db/rls/org_isolation.sql` se quiser
  paridade total).
- Não recebe dados reais de clientes. Não usar OFX/XML reais aqui.
