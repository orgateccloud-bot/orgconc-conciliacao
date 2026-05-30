# Deploy — OrgConc

> **Versão alvo:** ver [`VERSION`](./VERSION).
> Backend (FastAPI) e frontend (React/Vite) vivem no mesmo container — o React é compilado no build do Docker e servido pela API em `/app/`.

---

## 1. Topologia

```
┌─────────────────────────────────────────────────────────┐
│  Container OrgConc (Render / Railway / VPS)             │
│  ┌──────────────────────────────────────────────────┐   │
│  │  uvicorn api.main:app  (porta $PORT)             │   │
│  │  ├─ /v1/* ........ endpoints REST                │   │  ◄── HTTPS
│  │  ├─ /docs ........ Swagger                       │   │
│  │  ├─ /health ...... healthcheck                   │   │
│  │  ├─ /app/* ....... React SPA (orgconc-react/dist)│   │
│  │  └─ /ui/* ........ UI legada (static/, deprecated)│  │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
            │                              │
            ▼                              ▼
   ┌──────────────────┐          ┌──────────────────┐
   │  Supabase        │          │  Anthropic API   │
   │  (Postgres pooler│          │  (Claude 4.x)    │
   │   :6543 asyncpg) │          └──────────────────┘
   └──────────────────┘
            │
            ▼  (opcional, futuro)
   ┌──────────────────┐
   │  Redis (Upstash) │   ← rate-limit distribuído + fila Arq
   └──────────────────┘
```

---

## 2. Pré-requisitos

- **Python 3.12+** (Dockerfile usa `python:3.12-slim`)
- **Node 22+** (Dockerfile usa `node:22-alpine` para o build do React)
- **PostgreSQL** (Supabase recomendado; precisa do pooler na porta 6543)
- **Conta Anthropic** com créditos (`ANTHROPIC_API_KEY`)
- *(opcional, em produção)* **SERPRO** consumer key/secret ou demo token
- *(opcional)* **Redis** para rate-limit distribuído

---

## 3. Variáveis de ambiente

### 3.1 Obrigatórias em produção

Validadas no boot pelo [`api/core/config.py::_validate_production_env`](./api/core/config.py). Se faltarem, o processo **não sobe**.

| Variável | Descrição |
|---|---|
| `ANTHROPIC_API_KEY` | Chave da Anthropic (`sk-ant-...`) |
| `ORGCONC_JWT_SECRET` | Segredo JWT — **≥ 32 chars**. Gere com: `openssl rand -hex 32` |
| `ORGCONC_ADMIN_EMAIL` | Email do admin (usado em `/auth/login`) |
| `ORGCONC_ADMIN_SENHA_HASH` | bcrypt da senha (gere via `POST /auth/hash` em dev, com Bearer) |
| `ORGCONC_CORS_ORIGINS` | CSV de origens. Ex: `https://app.orgatec.cloud` |
| `ORGCONC_ENV` | `production` (libera as checagens estritas) |

### 3.2 Recomendadas

| Variável | Default | Descrição |
|---|---|---|
| `DATABASE_URL` | — | Connection string Postgres. Use o **pooler** Supabase (`:6543`). Aceita `postgres://`, `postgresql://`, `postgresql+asyncpg://`. |
| `ORGCONC_JWT_TTL_MIN` | `120` | TTL do access token em minutos |
| `ORGCONC_LOG_JSON` | `true` | `false` em dev para output legível |
| `ORGCONC_LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `ORGCONC_MAX_UPLOAD_MB` | `10` | Por arquivo |
| `ORGCONC_MAX_UPLOAD_TOTAL_MB` | `50` | Soma do request |
| `ORGCONC_DATA_DIR` | `./data` | Diretório dos datasets JSON (rolling 50) |

### 3.3 SERPRO (CPF/CNPJ)

Endpoints `/serpro/*` respondem **503** se nenhuma das modalidades abaixo estiver configurada:

| Variável | Quando usar |
|---|---|
| `ORGCONC_SERPRO_CLIENT_PATH` | Pasta com `serpro_client.py` (mantido fora do repo) |
| `ORGCONC_SERPRO_DEMO_TOKEN` | Modo demo (token fixo da doc) |
| `ORGCONC_SERPRO_CONSUMER_KEY` + `..._CONSUMER_SECRET` | Modo produção OAuth2 |
| `ORGCONC_SERPRO_CERT_FILE` + `..._KEY_FILE` | mTLS (e-CNPJ) se o contrato exigir |
| `ORGCONC_SERPRO_AUDIT_SALT` | **OBRIGATÓRIO em produção** — pepper para o hash de auditoria. Gere com `openssl rand -hex 32`. Sem ele, logs ficam vulneráveis a rainbow-table de CPFs. |
| `ORGCONC_SERPRO_TIMEOUT_S` | Default `15` |

### 3.4 Futuro (entrando nos próximos itens do roadmap)

| Variável | Item do roadmap |
|---|---|
| `REDIS_URL` | Item 3 (rate-limit distribuído) + Item 13 (fila Arq) |
| `SENTRY_DSN` | Item 19 |
| `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_KEY`, `S3_SECRET`, `ORGCONC_STORAGE_BACKEND` | Item 15 |

---

## 4. Build local (sem Docker)

```bash
# 1. Backend
python -m venv .venv && source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
# edite .env com suas chaves

# 2. Frontend (terminal separado, em modo dev com hot-reload)
cd orgconc-react
npm install
npm run dev                 # http://127.0.0.1:5173 (proxy para a API em :8765)

# 3. API
python -m uvicorn api.main:app --host 127.0.0.1 --port 8765 --reload
```

URLs:
- Swagger: <http://127.0.0.1:8765/docs>
- React dev: <http://127.0.0.1:5173>
- UI legada: <http://127.0.0.1:8765/ui/> (deprecated)

---

## 5. Build local servindo o React pela API

```bash
cd orgconc-react && npm run build      # gera orgconc-react/dist/
cd ..
python -m uvicorn api.main:app --host 0.0.0.0 --port 8765
```

URL: <http://127.0.0.1:8765/app/>

---

## 6. Build Docker

```bash
docker build -t orgconc:$(cat VERSION) .
docker run --rm -p 8765:8000 --env-file .env orgconc:$(cat VERSION)
```

Imagem final contém:
- Bundle React em `/app/orgconc-react/dist`
- Backend em `/app/api`
- Healthcheck em `/health`

`docker-compose.yml` na raiz sobe API + (futuramente) Redis.

---

## 7. Deploy em Render

1. **Settings → Environment** — preencha tudo de §3.1.
2. **Build Command:** *(deixe em branco — o Dockerfile cuida do build)*
3. **Start Command:** *(deixe em branco — `CMD` do Dockerfile cuida)*
4. **Health Check Path:** `/health`
5. **Auto-Deploy:** ativar para branch `main`.
6. `render.yaml` na raiz já está configurado.

---

## 8. Deploy em Railway

```bash
npm install -g @railway/cli
railway login
railway link            # ou: railway init
railway up
```

`railway.json` na raiz já está configurado.

Variáveis: `railway variables set ORGCONC_JWT_SECRET=...` para cada uma de §3.1.

---

## 9. Banco de dados (Supabase)

### 9.1 Setup inicial

1. Crie projeto em <https://supabase.com>.
2. SQL Editor → cole e execute o conteúdo de [`supabase/migrations/002_fix_uuid_types.sql`](./supabase/migrations/002_fix_uuid_types.sql).
   - O script é **idempotente**: se o schema correto já existir, não faz nada.
   - Se houver schema legado com `INTEGER` PKs, ele recria com `UUID`.
3. Em **Settings → Database → Connection string**, copie a URL do **pooler (porta 6543)** e cole em `DATABASE_URL`. O backend converte `postgresql://` para `postgresql+asyncpg://` automaticamente.

### 9.2 Schema atual

Tabelas vivas (criadas pela migration 002):
- `clientes (id UUID, nome, cnpj UNIQUE, email, telefone, plano, ativo, criado_em, atualizado_em)`
- `conciliacoes (id UUID, cliente_id FK, report_id UNIQUE, modo, totais..., criado_em)`
- `transacoes (id UUID, conciliacao_id FK CASCADE, cliente_id FK SET NULL, data_lancamento, valor, memo, categoria, banco, tipo, eh_anomalia, criado_em)`

Triggers: `set_atualizado_em()` em `UPDATE clientes`.

Índices: por `cliente_id`, `conciliacao_id`, `data_lancamento`, `eh_anomalia` (parcial), `criado_em`.

> Tabelas `ml_predicoes` e `fsrs_memorias` foram **removidas** na migration `002_drop_orphan_tables.py`. Não as recrie.

### 9.3 Alembic (incremental)

```bash
# Marca o banco existente como estando no baseline (rodou via SQL acima)
alembic stamp 001

# Novas migrations sao incrementais
alembic upgrade head
```

### 9.4 RLS (Row Level Security)

Hoje **não está configurado** — todos os dados são acessíveis com o JWT admin. Configurar RLS é o **Item 16/17** do roadmap (multi-tenancy + audit log).

---

## 10. Frontend deploy

O React é **servido pela mesma API** em `/app/` (após build Docker). Não há deploy separado para GitHub Pages, S3 ou CDN no setup atual.

**Roadmap (Item 24):** mover assets estáticos para CDN (Cloudflare) com cache imutável.

---

## 11. CI/CD

`.github/workflows/ci.yml` roda em cada PR:

| Job | O que faz |
|---|---|
| `backend` | Setup Python 3.12 → instala `requirements*.txt` → ruff → pytest com cov |
| `frontend` | Setup Node 22 → `npm ci` → `npm run typecheck` → `npm run lint` → `npm run build` |
| `e2e` | (futuro Item 21) Playwright contra stack docker-compose |

`.github/workflows/deploy.yml` é acionado em push na `main` para deploy automático.

---

## 12. Verificação pós-deploy

```bash
# 1. Health
curl https://<seu-host>/health
# resposta esperada: {"status":"ok","versao":"0.6.0","api_key_configured":true,"banco_dados":"ok"}

# 2. Versão (deve casar com VERSION local)
curl https://<seu-host>/ | jq .version
# 0.6.0

# 3. Login (admin)
curl -X POST https://<seu-host>/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@orgatec.cloud","senha":"...sua-senha..."}'
# resposta: {"access_token":"eyJ...","token_type":"bearer"}

# 4. Auth check com Bearer
curl https://<seu-host>/auth/me -H "Authorization: Bearer eyJ..."
# resposta: {"sub":"admin@...","email":"...","role":"admin"}

# 5. Smoke: lista clientes (requer DB)
curl https://<seu-host>/clientes -H "Authorization: Bearer eyJ..."

# 6. SPA está servida?
curl -I https://<seu-host>/app/
# esperado: 200 + content-type: text/html
```

---

## 13. Rollback

Hoje **não automatizado** (Item 25 do roadmap documenta o processo formal). Rollback manual:

1. **Render:** `Manual Deploy → Rollback to <previous-deploy>` na UI.
2. **Railway:** `railway redeploy --service <id>` apontando para o commit anterior.
3. **DB:** Supabase tem Point-in-Time Recovery no plano Pro. Em Free, restaurar do último backup automático (24h).

---

## 14. Troubleshooting

| Sintoma | Causa provável | Solução |
|---|---|---|
| Boot falha com `RuntimeError: ORGCONC_JWT_SECRET obrigatorio...` | Variável faltando em prod | Definir no painel do PaaS |
| `/health` retorna `banco_dados: "erro"` | DB URL inválida ou pooler fora | Verificar `DATABASE_URL`, ping na porta 6543 |
| `502 anthropic_error: credit balance` | Sem créditos | Recarregar em <https://platform.claude.com/settings/billing> ou usar `?simular=true` |
| `429 Too Many Requests` em multi-worker | Rate-limit in-memory por processo | Item 3 do roadmap: migrar para Redis |
| React não carrega em `/app/` | `orgconc-react/dist` não copiado | Rebuild Docker; conferir stage `frontend-builder` no Dockerfile |
| Login funciona mas requisições retornam 401 | JWT secret mudou entre workers | Definir `ORGCONC_JWT_SECRET` explícito (auto-gerado não sobrevive restart) |
| WeasyPrint quebra em PDF | Libs nativas faltando | Dockerfile já instala `libcairo2`, `libpango-*`, `libgdk-pixbuf*` |

---

## 15. Checklist de "production-ready"

- [ ] `VERSION` consistente com tag git
- [ ] Todas as env vars de §3.1 setadas
- [ ] `DATABASE_URL` usando pooler `:6543`
- [ ] CORS restrito (sem `*`)
- [ ] HTTPS forçado (`ORGCONC_ENV=production` ou `ORGCONC_HTTPS_ENABLED=1`) — HSTS é ativado
- [ ] `ORGCONC_SERPRO_AUDIT_SALT` configurado se SERPRO estiver ativo
- [ ] Senha admin com bcrypt forte (gerada via `/auth/hash`)
- [ ] `/health` reportando `ok` em todas as deps
- [ ] Backup Supabase confirmado
- [ ] Logs estruturados sendo coletados (CloudWatch/Grafana/Loki — Item 18)
- [ ] Sentry configurado (Item 19)

---

**Documentos relacionados:**
- [`README.md`](./README.md) — Visão geral
- [`analise_camadas_arquitetura.md`](./analise_camadas_arquitetura.md) — Estado atual vs alvo
- [`projeto_implementacao_completo.md`](./projeto_implementacao_completo.md) — Roadmap completo
- [`.env.example`](./.env.example) — Template de variáveis
