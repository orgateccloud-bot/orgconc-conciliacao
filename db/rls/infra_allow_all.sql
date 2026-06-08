-- RLS allow_all nas tabelas de INFRA/AUTH (NÃO tenant-scoped).
--
-- Estas tabelas não têm org_id e o isolamento delas NÃO é por organização — o
-- enforcement fica na camada de aplicação (ver db/rls/README.md §"tabelas de auth
-- fora da isolação"). Na era da "RLS nominal" elas tinham uma policy `allow_all`
-- (USING true) só para satisfazer o advisor do Supabase. O rollout de RLS real
-- (Fase B) dropou os `allow_all` mas só recriou `org_isolation` nas tabelas
-- tenant-scoped — deixando estas com RLS HABILITADA e ZERO policies, o que no
-- Postgres significa NEGAR TUDO para o role da aplicação (app_orgconc, NOBYPASSRLS).
-- Efeito: INSERT/UPDATE falham ("new row violates row-level security policy") e
-- SELECT retorna 0 linhas. Isso quebrou:
--   - ai_insights_cache  -> 500 em GET /ai/insights/dashboard
--   - refresh_tokens     -> login real (grava refresh token) e /auth/refresh (lê)
--   - orgs               -> admin lista 0 orgs; criar org falha
--   - audit_events       -> trilha de auditoria não grava (silencioso)
--   - llm_cost_daily     -> tracking de custo LLM não grava
--
-- Este script restaura o `allow_all` nelas (mantém RLS "habilitada" p/ o advisor,
-- mas permite o acesso do app — o isolamento real dessas continua na aplicação).
--
-- IDEMPOTENTE. Aplicar no Supabase como owner (postgres):
--   psql "$DATABASE_URL" -f db/rls/infra_allow_all.sql

DO $$
DECLARE
  t        text;
  tabelas  text[] := ARRAY[
    'ai_insights_cache', 'audit_events', 'llm_cost_daily', 'orgs', 'refresh_tokens'
  ];
BEGIN
  FOREACH t IN ARRAY tabelas LOOP
    IF to_regclass('public.' || t) IS NULL THEN
      RAISE NOTICE 'infra allow_all: tabela public.% ausente — pulando', t;
      CONTINUE;
    END IF;
    -- Mantém RLS habilitada (advisor) mas SEM force (owner/migrations bypassam).
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS allow_all ON public.%I', t);
    EXECUTE format(
      'CREATE POLICY allow_all ON public.%I FOR ALL USING (true) WITH CHECK (true)', t);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO app_orgconc', t);
  END LOOP;
END $$;
