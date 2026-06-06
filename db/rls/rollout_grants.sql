-- Grants para o role da aplicação (app_orgconc) — pré-requisito do FLIP da conexão.
--
-- Ao conectar como app_orgconc (NOBYPASSRLS) em vez de postgres, o backend precisa
-- de DML em TODAS as tabelas que usa — não só as tenant-scoped isoladas por RLS,
-- mas também as de auth/infra (usuarios, orgs, refresh_tokens, audit_events,
-- caches, datasets…). Sem isso: "permission denied".
--
-- A RLS (db/rls/org_isolation.sql) e estes grants são ortogonais: o grant LIBERA a
-- operação; a policy FILTRA as linhas. Tabelas SEM policy de org (usuarios, orgs,
-- refresh_tokens, …) ficam acessíveis sem isolamento por org — de propósito: o
-- login/refresh acontecem ANTES de haver contexto de org, e o enforcement dessas
-- continua na camada de aplicação.
--
-- IDEMPOTENTE. Aplicar no Supabase como owner (postgres):
--   psql "$DATABASE_URL" -f db/rls/rollout_grants.sql
-- Depois, definir a senha forte do role (NÃO versionar a senha):
--   ALTER ROLE app_orgconc PASSWORD '<senha-forte>';

GRANT USAGE ON SCHEMA public TO app_orgconc;

-- Blanket DML no schema inteiro (cobre auth/infra/fiscais + as tenant já isoladas).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_orgconc;

-- Tabelas futuras criadas por migrations (rodam como postgres) já nascem com o grant.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_orgconc;
