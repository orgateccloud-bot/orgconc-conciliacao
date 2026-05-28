# Runbook — Aplicação da Migration 006 (Integração Fiscal)

**Quem executa:** DevOps / DBA com acesso ao Supabase de staging/produção.
**Quem solicita:** time de produto ao aprovar PR `feature/integracao-fiscal`.
**Branch alvo:** `feature/integracao-fiscal` (ou `main` após merge).
**Migration arquivo:** `migrations/versions/006_fiscal_integration.py`.

## Resumo do que a migration faz

| Tabela | Linhas-de-mudança | Reversível |
|---|---|:---:|
| `documento_fiscal` | CREATE TABLE + 3 índices (`chave UNIQUE`, `emit_cnpj`, `data_emissao`) | Sim |
| `cruzamento_fiscal` | CREATE TABLE + 1 índice (`cliente_id, status`) | Sim |
| `conformidade_fornecedor` | CREATE TABLE + 2 índices (`cnpj UNIQUE`, `risco DESC`) | Sim |
| `carta_versao` | CREATE TABLE + 1 índice (`cliente_id, gerado_em DESC`) | Sim |

Total: **4 tabelas novas, 7 índices, 0 ALTER em tabelas existentes**. Migração aditiva, sem risco de quebrar dados atuais.

## Pré-checks (antes de rodar)

```bash
# 1. Confirmar branch
cd C:/OrgConc
git rev-parse --abbrev-ref HEAD        # esperado: feature/integracao-fiscal ou main

# 2. Confirmar revision atual no DB
alembic current
# Esperado ANTES da migration: 005 (head)
# Esperado APÓS: 006 (head)

# 3. Verificar que .env aponta para o ambiente certo
echo $DATABASE_URL | grep -o "supabase.com\|prod\|staging"
```

## Execução

### Staging (obrigatório antes de produção)

```bash
# 1. Backup pré-migration (Supabase faz automático, mas confirmar timestamp)
# Abrir: Supabase Console > Database > Backups
# Confirmar backup das últimas 24h existe.

# 2. Aplicar migration
alembic upgrade head

# Saída esperada:
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# INFO  [alembic.runtime.migration] Running upgrade 005 -> 006, Integração Fiscal

# 3. Confirmar versão
alembic current
# Esperado: 006 (head)
```

### Produção

Igual ao staging, mas:

1. Janela de manutenção (não é DOWN, mas DDL aciona lock leve em `clientes` por causa de FK)
2. Comunicação para o time pelo Slack/Discord 15 min antes
3. Monitorar Supabase Console > Database > Live Queries durante execução

## Smoke test pós-migration

Após `alembic current` retornar `006`, validar com SQL diretamente:

```sql
-- 1. Tabelas criadas
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('documento_fiscal','cruzamento_fiscal','conformidade_fornecedor','carta_versao')
ORDER BY table_name;
-- Esperado: 4 linhas

-- 2. Indices criados
SELECT indexname FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('documento_fiscal','cruzamento_fiscal','conformidade_fornecedor','carta_versao')
ORDER BY indexname;
-- Esperado: 7 índices + 4 PKeys (11 linhas total)

-- 3. Foreign keys ok
SELECT conname, conrelid::regclass AS tabela
FROM pg_constraint
WHERE contype = 'f'
  AND conrelid::regclass::text IN ('documento_fiscal','cruzamento_fiscal','conformidade_fornecedor','carta_versao');
-- Esperado: pelo menos 1 FK por tabela apontando para clientes/transacoes/documento_fiscal

-- 4. Sem dados (tabelas novas)
SELECT 'documento_fiscal' AS t, count(*) FROM documento_fiscal
UNION ALL SELECT 'cruzamento_fiscal', count(*) FROM cruzamento_fiscal
UNION ALL SELECT 'conformidade_fornecedor', count(*) FROM conformidade_fornecedor
UNION ALL SELECT 'carta_versao', count(*) FROM carta_versao;
-- Esperado: 4 linhas, todas com count = 0
```

## Smoke test via API (após migration)

```bash
# Subir backend localmente apontando para o DB migrado
uvicorn api.main:app --port 8765

# 1. Healthcheck
curl http://127.0.0.1:8765/health | jq .banco_dados
# Esperado: "ok"

# 2. Listar documentos (vazio, mas endpoint deve responder 200, não 500)
TOKEN="<seu_jwt>"
CLIENTE_ID="<uuid_de_um_cliente>"
curl -H "Authorization: Bearer $TOKEN" \
     "http://127.0.0.1:8765/fiscal/documentos/$CLIENTE_ID?limit=10"
# Esperado: {"cliente_id":"...","total":0,"documentos":[]}

# 3. Conformidade (vazio)
curl -H "Authorization: Bearer $TOKEN" \
     "http://127.0.0.1:8765/fiscal/conformidade/$CLIENTE_ID"
# Esperado: {"cliente_id":"...","total":0,"fornecedores":[]}

# 4. Risco tributário (zero)
curl -H "Authorization: Bearer $TOKEN" \
     "http://127.0.0.1:8765/fiscal/risco-tributario/$CLIENTE_ID"
# Esperado: {"risco_total_anual":0,"por_classe_risco":{...},"total_fornecedores":0}
```

## Rollback

Caso algo dê errado nos smoke tests, reverter:

```bash
alembic downgrade 005
```

A migration 006 tem `downgrade()` que faz `DROP TABLE` reverso. **Atenção:**
qualquer dado já inserido em produção será perdido. Por isso o teste em staging é obrigatório.

## Pontos de atenção

| Risco | Mitigação |
|---|---|
| Lock em `clientes` durante CREATE de FK | Migration roda em <2s; Supabase aguenta lock leve |
| Conflito de nome `documento_fiscal` se já existir | Pre-check: `SELECT 1 FROM pg_tables WHERE tablename = 'documento_fiscal'` deve retornar 0 |
| `gen_random_uuid()` indisponível | Confirmar extension: `CREATE EXTENSION IF NOT EXISTS pgcrypto` (Supabase já tem por padrão) |
| Alembic não tracked se for primeira migration aplicada | Verificar `alembic_version` table existe; se não, rodar `alembic stamp 005` antes |

## Sign-off

Quem rodou: _______________
Data/hora: _______________
Revision antes: _______ → depois: 006
Smoke tests passaram: [ ] sim [ ] não
PR merge autorizado: [ ] sim [ ] não
