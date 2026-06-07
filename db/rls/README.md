# RLS por organização (tenant = `org_id`) — rollout

Isolamento multi-tenant **no banco** (defense-in-depth), por organização (a firma
contábil). Hoje a RLS do OrgConc é **nominal** (`allow_all` / `USING (true)`): o
isolamento real está só na camada de aplicação. Estes artefatos trocam isso por
isolamento de verdade — **mas a ativação tem pré-requisitos** (abaixo).

> **Estado:** este diretório PREPARA a RLS real (SQL + infra de backend + testes).
> **NÃO está ativo em produção** — `main` continua com `allow_all` até o rollout
> ser executado no Supabase.

## Arquivos

| Arquivo | Papel |
|---|---|
| `contraparte_org_isolation.sql` | PoC do **mecanismo** numa tabela de demonstração (`contraparte`). Provado em `tests/test_rls_isolation.py`. |
| `org_isolation.sql` | Aplica o padrão nas **tabelas tenant-scoped**: `clientes`, `conciliacoes`, `transacoes`, `apuracao_cbs_ibs` + fiscais (`documento_fiscal`, `cruzamento_fiscal`, `conformidade_fornecedor`, `guia_tributo`, `contrato`, `carta_versao`, `transacao_disposicao` — `org_id` via **migration 020**). Provado em `tests/test_rls_real_tables.py`. |
| `rollout_grants.sql` | GRANT DML de `app_orgconc` em **todas** as tabelas (auth/infra/fiscais incluídas — senão "permission denied" ao trocar a conexão) + default privileges p/ tabelas futuras. |

Padrão da política (falha-**fechada**): `org_id = NULLIF(current_setting('app.org_id', true), '')::uuid`
em `USING` (leitura/update/delete) **e** `WITH CHECK` (escrita). Sem `app.org_id`
setado → comparação vira `NULL` → **zero linhas** (nunca "tudo").

**Superadmin (leitura cross-org, leitura-só):** uma policy SEPARADA `superadmin_read`
`FOR SELECT USING (current_setting('app.superadmin', true) = 'on')` permite que o
**admin por env** leia todas as orgs. Como é só `FOR SELECT`, INSERT/UPDATE/DELETE
continuam governados pela `org_isolation` estrita → escrita cross-org barrada
(leitura-só **estrutural**). O GUC `app.superadmin` só é setado pelo backend a partir
de um token com o claim `superadmin` (emitido apenas no login do env-admin).

## ⚠️ Pré-requisitos (por que ainda não ativamos)

1. **Multi-org no auth.** Hoje o login é um **admin único** (`ORGCONC_ADMIN_EMAIL`),
   cujo token **não tem `org_id`**. Sem usuários por organização não há quem isolar,
   e ativar agora jogaria o admin (sem org) na falha-fechada → **0 linhas → app
   quebrado**. É preciso introduzir `users(email, senha_hash, org_id, role)` e
   emitir o token com `org_id` (o `TokenPayload`/`emitir_token` já aceitam o campo).
2. **Backfill de `org_id`.** Linhas legadas com `org_id NULL` ficam invisíveis a
   todos após a ativação. Preencher antes de trocar o role.
3. **Tabelas fiscais só têm `cliente_id`** (`documento_fiscal`, `cruzamento_fiscal`,
   `conformidade_fornecedor`, `guia_tributo`, `contrato`, `carta_versao`). Precisam
   de estratégia (abaixo) antes de entrarem no esquema.

## Passo-a-passo do rollout (quando os pré-requisitos estiverem prontos)

1. **Migrations** (adiciona `org_id` à `apuracao_cbs_ibs`):
   ```bash
   alembic upgrade head    # inclui a 014
   ```
2. **Backfill** `org_id` (as que têm `cliente_id` herdam da `clientes`):
   ```sql
   UPDATE conciliacoes c SET org_id = cl.org_id FROM clientes cl
     WHERE c.cliente_id = cl.id AND c.org_id IS NULL;
   UPDATE transacoes  t SET org_id = cl.org_id FROM clientes cl
     WHERE t.cliente_id = cl.id AND t.org_id IS NULL;
   -- clientes.org_id e apuracao_cbs_ibs.org_id: preencher conforme a origem.
   ```
   Verifique que **não restam** `org_id IS NULL` nas tabelas a isolar.
3. **Aplicar grants + policies** (idempotente, como owner/`postgres`):
   ```bash
   psql "$DATABASE_URL" -f db/rls/rollout_grants.sql   # GRANT em todas as tabelas
   psql "$DATABASE_URL" -f db/rls/org_isolation.sql     # ENABLE+FORCE+policy nas tenant
   ```
4. **Senha forte** no role da aplicação:
   ```sql
   ALTER ROLE app_orgconc PASSWORD '<senha-forte>';
   ```
5. **Backend** passa a conectar como `app_orgconc` (NOBYPASSRLS), **não** `postgres`:
   - `DATABASE_URL=postgresql://app_orgconc:<senha>@<host>/<db>` (no flip de prod).
   - O contexto por request já está fiado: `RLSContextMiddleware`
     (`api/core/bootstrap.py`) decodifica o JWT e chama `set_org_context(org_id)`;
     o listener `after_begin` (`api/db/rls_context.py`) emite `SET LOCAL app.org_id`
     em **cada** transação. Tabelas de auth (`usuarios`, `orgs`, `refresh_tokens`)
     **não** entram na isolação (login acontece antes do contexto) — enforcement na app.
6. **Provar**: rodar os testes contra o banco (ver abaixo) e validar manualmente
   que um usuário de uma org não vê dados de outra.

### Tabelas fiscais (`cliente_id`, sem `org_id`) — duas opções

- **(A) Recomendada — desnormalizar:** adicionar `org_id` (migration) + backfill
  via `clientes` e incluí-las no `org_isolation.sql`. Policy direta e performática.
- **(B) Sem coluna nova — subquery:** policy
  `cliente_id IN (SELECT id FROM clientes WHERE org_id = NULLIF(current_setting('app.org_id', true), '')::uuid)`.
  Evita a coluna, mas é mais lenta e exige `GRANT SELECT ON clientes`.

## Como provar

```bash
# Postgres real necessário (o CI sobe um service postgres:16 no job `rls`).
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres
pytest tests/test_rls_isolation.py tests/test_rls_real_tables.py -v
```
Sem `DATABASE_URL`, os testes **skipam** (não falham).

## Rollback

Reverter para `allow_all` (ou desligar a RLS) numa tabela:
```sql
DROP POLICY IF EXISTS org_isolation ON public.<tabela>;
CREATE POLICY allow_all ON public.<tabela> FOR ALL USING (true) WITH CHECK (true);
-- e o backend volta a conectar como o role owner (postgres).
```
