# BACKUP — OrgConc

Estratégia de backup e restore. Cobrindo banco (Supabase), datasets locais e segredos.

## RTO/RPO

| Dado | RPO (perda aceitável) | RTO (tempo de recuperação) |
|---|---|---|
| PostgreSQL Supabase | 24h | 4h |
| Datasets JSON locais | 0h (efêmero, reproduzível) | n/a |
| Segredos (.env) | 0h | 1h (passo manual no provedor) |

## PostgreSQL (Supabase)

### Backup automático

Supabase faz backup diário automático no plano Free (7 dias retention) e Pro (30 dias). Confirme em:
```
Supabase Dashboard → Project → Database → Backups
```

Se estiver no plano Free e precisar de retention maior, configure backup manual semanal:
```bash
# Em uma máquina com acesso ao banco
pg_dump "postgresql://postgres.xxx:senha@aws-1-sa-east-1.pooler.supabase.com:6543/postgres" \
  --no-owner --no-acl \
  --file=backups/orgconc-$(date +%Y%m%d).sql

# Comprima e suba para storage seguro (S3 / GCS / Backblaze B2)
gzip backups/orgconc-$(date +%Y%m%d).sql
aws s3 cp backups/orgconc-$(date +%Y%m%d).sql.gz s3://orgconc-backups/db/
```

Agende via cron ou GitHub Actions (workflow `.github/workflows/backup-db.yml` — TODO).

### Restore

```bash
# 1. Crie projeto Supabase novo (ou use o staging)
# 2. Pegue o connection string novo
# 3. Restore
gunzip -c orgconc-20250525.sql.gz | psql "postgresql://...novo..."
# 4. Rode migrations pendentes (se houver)
alembic upgrade head
# 5. Smoke test
curl -s https://api.orgconc.com/health | jq
# 6. Atualize DATABASE_URL no provedor de prod
```

### Point-in-time recovery (PITR)

Supabase Pro tem PITR: Supabase Dashboard → Project → Settings → Database → PITR. Aciona em interface; restore para o momento exato T.

## Datasets JSON locais

Não são fonte autoritativa — são cache do output de cada conciliação para download posterior dos exports (HTML/XLSX/PDF). Localização:
```
./data/{report_id}.json
```

Política:
- **Sem backup ativo** (são reproduzíveis se o usuário rodar a conciliação de novo).
- Em produção, montar volume persistente (Railway volume / Render disk) com pelo menos 10GB.
- Limpar arquivos >30 dias via cron:
  ```bash
  find ./data -name "*.json" -mtime +30 -delete
  ```

## Segredos

Mantenha duas cópias:

1. **Operacional**: nos painéis dos provedores (Railway/Render env vars, Supabase keys, Anthropic console).
2. **Backup**: gerenciador de senhas do owner (1Password / Bitwarden), label `orgconc-secrets-YYYY-MM-DD`.

Rotação:
- `ORGCONC_JWT_SECRET`: rotacione a cada 6 meses ou após incidente (invalida todas as sessões — comunique antes).
- `ANTHROPIC_API_KEY`: rotacione a cada 12 meses ou ao detectar uso indevido.
- `SUPABASE` service role key: nunca exponha — use apenas via env do backend.

## Disaster Recovery — passo a passo

Cenário pior: Supabase down + Railway down ao mesmo tempo.

1. Provisione novo Supabase (region diferente, ex: us-east-1).
2. Restore do backup mais recente (`pg_dump`).
3. Provisione backend em Render ou Fly.io (provedor alternativo).
4. Copie env vars do gerenciador de senhas + atualize `DATABASE_URL`.
5. Atualize DNS (`api.orgconc.com` → novo host).
6. Smoke test (`/health`, login, conciliação simulada).
7. Comunique usuários (status page / email).

ETA esperado: 4h se tudo manual; 1h se houver Terraform configurado (TODO).

## Checklist mensal

- [ ] Confirmar que backup automático Supabase está ocorrendo (Dashboard)
- [ ] Testar restore em ambiente isolado (uma vez por trimestre)
- [ ] Verificar que segredos no gerenciador estão atualizados
- [ ] Revisar `./data/*.json` antigos (limpar >30 dias)
- [ ] Checar tamanho do banco e custo Supabase
