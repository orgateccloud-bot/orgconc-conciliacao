# Runbook — OrgConc

> Procedimentos operacionais. Cada cenário: sintoma → diagnóstico → ação.

## Índice

1. [API não sobe](#1-api-não-sobe)
2. [`/health` reporta `degraded` ou `down`](#2-health-reporta-degraded-ou-down)
3. [Login retorna 503](#3-login-retorna-503)
4. [Conciliação retorna 502 anthropic](#4-conciliação-retorna-502-anthropic)
5. [Rate-limit 429 em multi-worker](#5-rate-limit-429-em-multi-worker)
6. [Worker Arq parou de processar](#6-worker-arq-parou-de-processar)
7. [Datasets sumiram após redeploy](#7-datasets-sumiram-após-redeploy)
8. [Rollback de release](#8-rollback-de-release)

---

## 1. API não sobe

**Sintoma:** container em `unhealthy`, logs com `RuntimeError`.

**Diagnóstico:**
```bash
docker logs orgconc-api | head -50
```

**Causa comum:** variáveis obrigatórias faltando em prod (`_validate_production_env`).

**Ação:**
- Conferir no painel do PaaS as 6 envs de §3.1 do [`DEPLOY.md`](../DEPLOY.md).
- `ORGCONC_JWT_SECRET` precisa ter ≥ 32 chars. Gere: `openssl rand -hex 32`.

---

## 2. `/health` reporta `degraded` ou `down`

```bash
curl -fsS https://<host>/health | jq
```

Olhe `dependencies.<dep>.status`:

| Dep | `down` significa |
|---|---|
| `database` | Pooler Supabase fora ou `DATABASE_URL` errada |
| `redis` | Redis caiu ou `REDIS_URL` errada |
| `anthropic` | `ANTHROPIC_API_KEY` ausente/inválida (não testa rede) |
| `data_dir` | `< 50 MB` livre no volume |

**Ação por dep:**
- `database`: verificar status no painel Supabase; rolar `DATABASE_URL` se senha rotada.
- `redis`: `docker compose up -d redis` (local) ou painel Upstash.
- `data_dir`: limpar `data/` ou aumentar volume.

---

## 3. Login retorna 503

`{"detail":"Auth nao configurada — defina ORGCONC_ADMIN_EMAIL e ORGCONC_ADMIN_SENHA_HASH no .env"}`

**Ação:**
1. Gere hash da senha em dev local (com auth Bearer no header):
   ```bash
   curl -X POST http://localhost:8765/auth/hash \
     -H "Authorization: Bearer dev-token" \
     -H "Content-Type: application/json" \
     -d '{"senha":"escolhaUmaForteAqui"}'
   ```
2. Configure `ORGCONC_ADMIN_EMAIL` e `ORGCONC_ADMIN_SENHA_HASH` no PaaS.
3. Reinicie a API.

---

## 4. Conciliação retorna 502 anthropic

Mensagens possíveis em `detail.anthropic_error`:

| Mensagem | Causa | Ação |
|---|---|---|
| `Saldo de creditos Anthropic esgotado` | Conta sem crédito | Recarregar em <https://platform.claude.com/settings/billing> |
| `Rate limit da Anthropic atingido` | Burst > limite | Aguardar 30s; reduzir paralelismo do multi-modelo |
| `Timeout na API Claude (90s)` | LLM lento | Migrar para fila Arq (Item 13 do roadmap) ou usar `?modelo=haiku` |

---

## 5. Rate-limit 429 em multi-worker

**Sintoma:** clientes legítimos recebem 429 esporádicos.

**Causa:** rate-limit ainda in-memory (`REDIS_URL` vazio).

**Ação:**
```bash
# Adicione REDIS_URL no painel do PaaS
REDIS_URL=rediss://default:<token>@<endpoint>.upstash.io:6379
```

Reinicie a API. Logs devem mostrar `Rate-limit storage: redis`.

---

## 6. Worker Arq parou de processar

**Sintoma:** jobs ficam em `queued` indefinidamente.

**Diagnóstico:**
```bash
docker logs orgconc-worker
redis-cli -u $REDIS_URL llen arq:queue:default
```

**Ações:**
- Worker caiu: `docker compose up -d worker`.
- Backlog enorme: aumentar `max_jobs` em `api/workers/settings.py`.
- Job preso: matar com `redis-cli -u $REDIS_URL del arq:job:<id>`.

---

## 7. Datasets sumiram após redeploy

**Sintoma:** `/export/*/{rid}` retorna 404 em datasets recentes.

**Causa:** Local FS sem volume persistente no PaaS.

**Ações:**
- **Curto prazo:** anexar volume persistente ao container, montando em `/app/data`.
- **Definitivo:** migrar para storage S3 (Item 15, já pronto):
  ```env
  ORGCONC_STORAGE_BACKEND=s3
  S3_BUCKET=orgconc-prod
  S3_ENDPOINT_URL=https://<projeto>.supabase.co/storage/v1/s3
  AWS_ACCESS_KEY_ID=...
  AWS_SECRET_ACCESS_KEY=...
  ```

---

## 8. Rollback de release

### Render

1. Dashboard → projeto → **Manual Deploy** → **Rollback to <previous>**.
2. Aguardar health check verde.
3. Comunicar no #incidents.

### Railway

```bash
railway redeploy --service <id> --commit <SHA_anterior>
```

### Banco

Supabase Pro: Point-in-Time Recovery (até 7d).
Supabase Free: restore do último daily backup.

**Atenção:** se houver migration nova entre o release atual e o alvo, **NÃO** faça rollback de DB sem `alembic downgrade` correspondente. Em dúvida, manter o DB e fazer fix-forward.

---

## Contatos de escalação

- Owner técnico: orgatec.cloud@gmail.com
- Status page: (definir)
- Slack: (definir)
