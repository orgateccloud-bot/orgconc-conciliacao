# RUNBOOK — OrgConc

Guia operacional para resposta a incidentes em produção. Mantenha curto e acionável.

## Contatos

| Função | Quem | Como |
|---|---|---|
| On-call primário | ORGATEC owner | orgatec.cloud@gmail.com |
| Provedor LLM | Anthropic Status | https://status.anthropic.com |
| Banco | Supabase Status | https://status.supabase.com |
| Hosting backend | Railway / Render Status | https://status.railway.app |

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
1. Veja logs no provedor (Railway/Render dashboard).
2. Se `init_sentry` falhou no startup: erro de DSN ou rede — remova `SENTRY_DSN` e suba sem.
3. Se DB unreachable: confira `DATABASE_URL` no painel + status Supabase.
4. Se Anthropic API key inválida: o app sobe mas requests `/conciliar/*` falham com 502.

Rollback (último recurso):
```bash
git checkout <SHA_VERSAO_ANTERIOR>
git push origin main --force-with-lease  # SO se voce e' o owner e ninguem mais
# Ou via Railway: redeploy da versao anterior pelo dashboard
```

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

### 5. DB indisponível

`DB_DISPONIVEL=False` durante startup → app sobe normalmente, mas endpoints `/clientes`, `/conciliacoes` retornam 503. Conciliações funcionam em modo JSON local (`./data/{rid}.json`).

Para forçar reconexão sem restart:
- Não é suportado hoje. Restart é necessário (`_db_ping_sync` roda apenas no import).

## Deploy

### Backend (Railway/Render)

1. `git push origin main` dispara deploy automático.
2. Healthcheck `/health` deve responder em <30s.
3. Variáveis obrigatórias em prod: `ORGCONC_ENV=production`, `ORGCONC_JWT_SECRET` (>=32 chars), `ORGCONC_ADMIN_EMAIL`, `ORGCONC_ADMIN_SENHA_HASH`, `ANTHROPIC_API_KEY`, `ORGCONC_CORS_ORIGINS`, `DATABASE_URL`.

### Frontend (GitHub Pages)

1. `git push origin main` aciona `.github/workflows/deploy.yml`.
2. Build `npm run build` em `orgconc-react/dist/` é publicado.
3. URL: `https://<org>.github.io/<repo>/app/`.

## Rollback de versão

```bash
# Lista as últimas tags
git tag --sort=-creatordate | head -10

# Identifica a versão anterior estável
git checkout v0.4.x
# Crie branch de hotfix se for permanente
git checkout -b hotfix/rollback-vX
# Push
git push origin hotfix/rollback-vX
# No painel do provedor, faça deploy desta branch
```

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
