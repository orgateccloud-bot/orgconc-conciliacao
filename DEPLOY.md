# Guia de Deploy — Orgconc

## URLs do Projeto

- **App (frontend + API):** servido pelo **Railway** — o React é buildado na imagem Docker e servido pelo FastAPI em `/app` (mesma origem da API).
- **Repositório:** https://github.com/orgateccloud-bot/orgconc-conciliacao

---

## 1. Frontend (React) — servido pelo Railway

O frontend é o SPA **React** em `orgconc-react/`, servido na **mesma origem** da API
(o `api.ts` chama a API por caminhos relativos + usa cookie httpOnly de refresh, então
servir cross-origin não é uma opção). O `Dockerfile` é **multi-stage**: um estágio Node
roda `npm ci && npm run build` e o `dist` resultante é copiado para a imagem Python em
`orgconc-react/dist`. O FastAPI monta esse build em `/app`. Sem o build (ex.: em CI),
`/app` responde **503** explícito — nunca serve UI legada.

> O deploy no GitHub Pages foi **removido**: o `base: "/app/"` do Vite não casa com a
> URL do Pages, e de lá o React não conseguiria falar com a API (origem diferente).

**Desenvolvimento local:**
```bash
cd orgconc-react
npm install
npm run dev          # Vite em http://127.0.0.1:5176, proxy da API para :8765
```

---

## 2. Backend (API FastAPI)

### Pré-requisitos
- Python 3.11+
- Conta no [Railway](https://railway.app), [Render](https://render.com) ou servidor próprio

### Deploy no Railway (recomendado)

#### Automático (CI/CD — preferido)

O job `deploy-backend` em `.github/workflows/deploy.yml` faz deploy a cada push
na `main`, **após** os testes de backend passarem (Python 3.12). Em seguida roda
um smoke test que aguarda até 5 min pelo `/health` retornar 200 antes de marcar
o deploy como bem-sucedido.

Configure no GitHub (Settings → Secrets and variables → Actions):

| Tipo | Nome | Valor |
|---|---|---|
| Secret | `RAILWAY_TOKEN` | Token do projeto Railway (`railway login` → account token) |
| Variable | `RAILWAY_SERVICE` | Nome do serviço backend no Railway |
| Variable | `PROD_HEALTH_URL` | URL pública do `/health` (ex.: `https://api.orgconc.com/health`) |

Sem esses valores o job é pulado; o deploy manual abaixo continua válido.

#### Manual

```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login e deploy
railway login
railway init
railway up
```

### Deploy Manual (Servidor/VPS)

```bash
# Clonar repositório
git clone https://github.com/orgateccloud-bot/orgconc-conciliacao.git
cd orgconc-conciliacao/api

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp ../.env.example .env
nano .env  # Preencher valores abaixo

# Iniciar servidor
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Variáveis de Ambiente Obrigatórias

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Banco de dados
DATABASE_URL=postgresql://user:pass@host:5432/orgconc

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Autenticação (a app usa ORGCONC_JWT_SECRET; >= 32 chars, OBRIGATORIO em producao)
# Gere com: openssl rand -hex 32
ORGCONC_JWT_SECRET=
ORGCONC_ENV=production

# Admin
ORGCONC_ADMIN_EMAIL=admin@empresa.com
ORGCONC_ADMIN_SENHA_HASH=bcrypt-hash

# CORS (separar por vírgula)
ORGCONC_CORS_ORIGINS=https://orgateccloud-bot.github.io,http://localhost:3000

# Upload
ORGCONC_MAX_UPLOAD_MB=50
ORGCONC_MAX_UPLOAD_TOTAL_MB=500

# Servidor
HOST=0.0.0.0
PORT=8000
WORKERS=2
```

### Ambiente de staging (Railway)

Existe um environment **staging** no mesmo projeto Railway (serviço
`web-staging` + Postgres próprio do Railway, separado do Supabase de prod).
Uso principal: **validar migrations Alembic antes de produção**.

```bash
railway environment staging        # troca o contexto da CLI
railway up                         # deploy manual da branch atual no staging
```

Particularidades do staging:
- O banco foi **bootstrapado** com `create_all` + `alembic stamp head` — as
  migrations antigas NÃO são re-executáveis do zero ali; valide apenas as
  migrations NOVAS (upgrade incremental a partir do head).
- asyncpg exige **1 statement por `op.execute()`** — migration com múltiplos
  comandos num único execute passa no SQLite/psycopg2 e quebra no staging/prod.
- Staging não tem RLS de prod nem dados reais — não serve para validar
  isolamento de tenant (use os testes `tests/test_rls_*.py` no CI para isso).

Fluxo recomendado para migration de risco: deploy no staging → `alembic
upgrade head` lá → smoke test → só então merge na main (deploy de prod roda a
migration via `preDeployCommand`).

---

## 3. Supabase — Configuração

### Criar Projeto Supabase
1. Acessar https://supabase.com e criar conta
2. Criar novo projeto: **orgconc**
3. Anotar **Project URL** e **anon key** (Settings > API)

### Provisionar o schema (Supabase SQL + Alembic)

O schema é provisionado em **duas etapas**: o SQL base do Supabase + as migrations
Alembic incrementais. (NÃO existe `supabase/setup.sql` — use os arquivos abaixo.)

```bash
# 1. No SQL Editor do Supabase, aplicar NESTA ORDEM:
#    supabase/migrations/001_schema_inicial.sql   # clientes, conciliacoes, transacoes
#    supabase/migrations/002_fix_uuid_types.sql

# 2. Marcar o baseline e aplicar as migrations incrementais (Alembic):
export DATABASE_URL=postgresql://...    # connection string do pooler Supabase (porta 6543)
alembic stamp 001       # baseline: assume que o SQL do passo 1 já foi aplicado
alembic upgrade head    # aplica 003 (audit_events) → 007 (orgs, llm_cost_daily,
                        # guia_tributo, contrato, transacao_disposicao + org_id)
```

> **Importante:** sem o passo 2 o schema fica **incompleto** (faltam audit_events,
> tabelas fiscais, orgs, etc.). A migration 007 é idempotente.
> **Valide** com `alembic check` que `models.py` bate com o banco (diff vazio).

Tabelas resultantes: `orgs`, `clientes`, `conciliacoes`, `transacoes`,
`audit_events`, `ai_insights_cache`, `llm_cost_daily`, `guia_tributo`, `contrato`,
`transacao_disposicao`, `documento_fiscal`, `cruzamento_fiscal`,
`conformidade_fornecedor`, `carta_versao`.

### Políticas de Segurança (RLS)

**Fonte de verdade: [`db/rls/`](db/rls/)** — não copie SQL deste documento.
O isolamento multi-tenant é por `org_id` (policy `org_isolation`, GUC
`app.org_id`, role `app_orgconc` NOBYPASSRLS, FORCE RLS), ativo em produção
desde 2026-06-07. Para provisionar um ambiente novo:

```bash
# Na ordem, com a URL de OWNER (não a de runtime):
psql "$DATABASE_URL_OWNER" -f db/rls/rollout_grants.sql
psql "$DATABASE_URL_OWNER" -f db/rls/org_isolation.sql
psql "$DATABASE_URL_OWNER" -f db/rls/contraparte_org_isolation.sql
psql "$DATABASE_URL_OWNER" -f db/rls/infra_allow_all.sql
```

> ⚠️ Policies como `USING (auth.role() = 'authenticated')` ou `USING (true)`
> em tabelas de negócio **anulam o isolamento entre escritórios** — nunca as
> use fora das tabelas de infra listadas em `infra_allow_all.sql`.

---

## 4. GitHub Secrets (para CI/CD)

Configurar em **Settings > Secrets and variables > Actions**:

| Secret | Descrição |
|--------|-----------|
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_ANON_KEY` | Chave anon do Supabase |
| `JWT_SECRET` | Segredo JWT (mín. 32 chars) |
| `ORGCONC_AUTH_TOKEN` | Token de autenticação da API |

---

## 5. Conectar Frontend ao Backend

O SPA React (`orgconc-react`) chama a API por caminhos relativos (`/auth/...`,
`/conciliar/...`). Em desenvolvimento o Vite faz proxy para `http://127.0.0.1:8765`
(ver `orgconc-react/vite.config.ts`). Em produção, sirva o build na **mesma origem**
da API (mount `/app` do FastAPI) ou configure um proxy/redirect para o backend.

Garanta que `ORGCONC_CORS_ORIGINS` (backend) inclua a origem do frontend.

---

## 6. Verificação Final

```bash
# Testar health do backend
curl https://seu-backend.railway.app/health

# Testar login
curl -X POST https://seu-backend.railway.app/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@empresa.com","senha":"suasenha"}'
```

**Resposta esperada do /health** (estrutura real; `banco_dados` fica `skip` se sem DB):
```json
{
  "status": "ok",
  "versao": "0.5.0",
  "banco_dados": "ok",
  "api_key_configured": true,
  "dependencies": { "database": {"status": "ok"}, "anthropic": {"status": "ok"} }
}
```
