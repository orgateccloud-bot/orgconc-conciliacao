# RUNBOOK — OrgConc

Guia operacional para resposta a incidentes em produção. Mantenha curto e acionável.

## Contatos

| Função | Quem | Como |
|---|---|---|
| On-call primário | ORGATEC owner | orgatec.cloud@gmail.com |
| Provedor LLM | Anthropic Status | https://status.anthropic.com |
| Banco | Supabase Status | https://status.supabase.com |
| Hosting | Railway Status | https://status.railway.app |

## Alertas (Sentry)

Quando `SENTRY_DSN` está ativo, eventos de `level=error` ou superior disparam alerta. Veja [MONITORING.md](MONITORING.md) para configurar.

## Procedimentos

### 1. API caiu (5xx em todas as requests)

```bash
# Confirme com healthcheck
curl https://api.orgconc.com/health
# Se nao responde: provedor caiu OU container nao subiu
```

Diagnóstico rápido:
1. Veja logs no Railway (dashboard do serviço).
2. Se `init_sentry` falhou no startup: erro de DSN ou rede — remova `SENTRY_DSN` e suba sem.
3. Se DB unreachable: confira `DATABASE_URL` no painel + status Supabase.
4. Se Anthropic API key inválida: o app sobe mas requests `/conciliar/*` falham com 502.
5. Se o app responde mas está lento: `curl https://api.orgconc.com/metrics` e
   verifique `orgconc_http_requests_in_progress` (concorrência travada) e a
   distribuição de `orgconc_http_request_duration_seconds`. Ver [MONITORING.md](MONITORING.md) §3.

Rollback (último recurso): Railway → **Deployments** → deployment anterior → **"Redeploy"**.
Ver [Rollback de versão](#rollback-de-versão).

### 2. Custo LLM disparou

Se aparecer log `llm_custo_threshold_atingido` (alerta diário):

```bash
# Verifique top consumidores pelo log estruturado
# Cada llm_uso tem: llm_model, llm_cost_total_usd, request_id

# Curto prazo: reduza threshold ou ative simular=true
# Sem deploy: reduza o limite via env e restart
ORGCONC_LLM_COST_ALERT_USD=5
```

Investigação:
1. Quem está chamando? Filtre logs por `request_id` → cruze com login (`user.sub`).
2. Está em loop? Algum cliente fazendo retry sem backoff?
3. Modelo errado? Forçar haiku temporariamente: `?modelo=haiku`.

### 3. Pico de requests / Rate limit

Slowapi já protege com 120/min global, 20/min upload, 5/min auth. Se ainda assim sobrecarregar:

1. Aumente recurso no provedor (vertical scale).
2. Habilite Cloudflare na frente (cache + DDoS).
3. Bloqueie IPs específicos via firewall do provedor.

### 4. Vazamento de PII suspeito

`mask_pii()` cobre CPF, CNPJ, email, último octeto de IP em logs JSON. Se algo escapou:

1. Identifique padrão não coberto (ex: telefone, RG).
2. Adicione regex em `api/services/logging_estruturado.py:_*_RE`.
3. Sentry `before_send` em `api/core/observability.py` aplica o mesmo `mask_pii`.
4. Para logs já enviados ao Sentry: use API de delete events.

### 5. DB indisponível (runtime sem banco)

`DB_DISPONIVEL=False` no startup → o app sobe, mas login de usuários de org, refresh e
`/clientes`/`/conciliacoes` retornam 503; só o admin-env loga. Conciliações funcionam em
modo JSON local (`./data/{rid}.json`). ⚠️ O `/health` de prod responde `{"status":"ok"}`
MESMO sem banco — não use como sonda.

**Sonda (sem credencial):**

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST https://<dominio>/auth/refresh
# 503 = runtime sem DB · 401 = DB ok (recusou por falta de cookie — esperado)
```

O monitor sintético roda essa sonda a cada 30min desde o #123.

Diagnóstico (incidente real de 2026-06-10 — ver
`docs/postmortems/2026-06-10-prod-sem-db-senha-app-orgconc.md`):
1. Logs do startup agora mostram o erro do ping (`Ping do DB falhou: ...`) — leia-o primeiro.
2. **Migrations passam mas o runtime falha?** Compare `DATABASE_URL` (user `app_orgconc.<ref>`)
   × `ALEMBIC_DATABASE_URL` (owner) — rotação parcial de senha é a causa clássica.
3. Senha divergente/credencial inválida: siga o procedimento completo do **§6** abaixo.
4. **Projeto Supabase free PAUSADO** (caso comum): TCP/REST do Supabase
   continuam respondendo, mas o handshake Postgres dá timeout. Solução: retomar o projeto
   no dashboard do Supabase e reiniciar o backend. Host direto `db.<ref>.supabase.co` não
   resolve mais; use só o pooler.

Para forçar reconexão sem restart: não é suportado (`_db_ping_sync` roda só no lifespan).
Restart/redeploy é necessário.

### 6. Credencial de DB inválida / rotação de senha do app_orgconc

Sintomas: app de pé, `/health` pode responder `{"status":"ok"}`, mas endpoints que dependem
de banco retornam 503; nenhum erro óbvio no boot (o ping de DB falha de forma silenciosa).
Migrations no preDeploy podem continuar passando (usam `ALEMBIC_DATABASE_URL`, owner) —
o que mascara o problema.

**Sonda de diagnóstico (sem credencial):**

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST https://<dominio>/auth/refresh
# 503 = backend sem DB · 401 = DB ok (recusou por falta de cookie — esperado)
```

**Rotação segura de senha do `app_orgconc`:**

1. `ALTER ROLE app_orgconc PASSWORD '<nova>';` no SQL editor do Supabase (conexão owner).
2. Atualize `DATABASE_URL` no Railway (service → **Variables**) com a senha nova.
3. Aguarde ~30s — o Supavisor (pooler) cacheia a credencial e rejeita a senha nova nesse
   intervalo (teste imediato falhar NÃO é sinal de erro).
4. Redeploy/restart do serviço.
5. Repita a sonda até responder **401**.

Execute os passos 1–5 na MESMA janela: rotação parcial (um lado atualizado sem o outro) foi
a causa raiz do incidente de ~32h sem banco. Rotação planejada (não-incidente) segue
`docs/ROTACAO_SEGREDOS.md` §2. Post-mortem completo:
`docs/postmortems/2026-06-10-prod-sem-db-senha-app-orgconc.md`.

## Deploy

### Backend + frontend (Railway, deploy único)

1. `git push origin main` dispara o deploy nativo do Railway: build do Dockerfile
   multi-stage (o build React sai no mesmo deploy, servido pela própria API em `/app`) →
   preDeployCommand `alembic upgrade head` → healthcheck `/health` (deve responder em <30s).
2. Variáveis obrigatórias em prod: `ORGCONC_ENV=production`, `ORGCONC_JWT_SECRET` (>=32 chars), `ORGCONC_ADMIN_EMAIL`, `ORGCONC_ADMIN_SENHA_HASH`, `ANTHROPIC_API_KEY`, `ORGCONC_CORS_ORIGINS`, `DATABASE_URL`.
3. Netlify gera apenas deploy-preview de PRs (dashboard-only, sem backend — não é produção).

## Rollback de versão

**Caminho primário — Railway (redeploy de build anterior):**

1. Dashboard → service → **Deployments** → escolha o deployment anterior estável →
   **"Redeploy"**. Ou via CLI: `railway redeploy`.
2. Confirme com `/health` e a sonda do §6 (espera-se **401**).
3. ⚠️ Redeploy NÃO desfaz migration já aplicada (`alembic upgrade head` rodou no preDeploy
   da versão nova) — se o schema mudou, avalie compatibilidade antes.

**Fallback — branch de hotfix a partir de tag (rollback permanente):**

```bash
git tag --sort=-creatordate | head -10   # lista as últimas tags
git checkout v0.4.x                      # versão anterior estável
git checkout -b hotfix/rollback-vX
git push origin hotfix/rollback-vX
# No Railway, aponte o serviço para essa branch e dispare o deploy
```

Nunca use force-push na `main` como rollback (reescreve história compartilhada e
dessincroniza worktrees/PRs abertos).

## Pós-incidente

Após qualquer incidente, escreva um post-mortem curto em `docs/postmortems/YYYY-MM-DD-<slug>.md`:
- O que aconteceu (timeline)
- Impacto (quanto tempo, quem foi afetado)
- Causa raiz
- O que mudou para evitar (link para PR)

## Referências

- [MONITORING.md](MONITORING.md) — alertas, dashboards, SLO
- [BACKUP.md](BACKUP.md) — backup e restore
- [DEPLOY.md](DEPLOY.md) — instruções de deploy detalhadas
