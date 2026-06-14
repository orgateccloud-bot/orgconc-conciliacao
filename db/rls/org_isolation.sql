-- RLS REAL por organização (tenant = org_id) nas tabelas tenant-scoped reais.
--
-- Estende o PoC (db/rls/contraparte_org_isolation.sql) das tabelas de demonstração
-- para as tabelas DO APP que já têm a coluna org_id: clientes, conciliacoes,
-- transacoes, apuracao_cbs_ibs. Substitui o padrão "allow_all" (USING (true)) por
-- isolamento de verdade por org.
--
-- ⚠️  ESTE SCRIPT PREPARA, NÃO ATIVA POR SI SÓ. Para o isolamento valer é preciso:
--   1. o backend conectar com o role app_orgconc (NOBYPASSRLS) — NÃO com postgres;
--   2. `SET LOCAL app.org_id = '<uuid-da-org>'` no início de cada transação;
--   3. existir multi-org no auth (hoje é admin-único) e org_id preenchido (backfill).
-- Ver db/rls/README.md (passo-a-passo + pré-requisitos).
--
-- Falha-FECHADA: sem app.org_id setado, current_setting(...,true) = NULL → a
-- comparação vira NULL (≡ falso) → zero linhas (nunca "tudo"). Linhas legadas com
-- org_id NULL ficam invisíveis a todos até o backfill.
--
-- IDEMPOTENTE. Aplicar no Supabase como owner (postgres):
--   psql "$DATABASE_URL" -f db/rls/org_isolation.sql
-- A prova automatizada está em tests/test_rls_real_tables.py.

-- 1. Role da aplicação (NOBYPASSRLS): a RLS se aplica a ele.
--    Troque a senha no rollout: ALTER ROLE app_orgconc PASSWORD '...'.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_orgconc') THEN
    CREATE ROLE app_orgconc LOGIN PASSWORD 'CHANGE_ME_NO_ROLLOUT' NOBYPASSRLS;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO app_orgconc;

-- 2. Aplica ENABLE+FORCE RLS, default de org_id pelo contexto, policy de
--    isolamento e GRANTs em cada tabela tenant-scoped que tenha a coluna org_id.
--    Tabela ausente (ambiente sem a migration) é pulada com NOTICE.
DO $$
DECLARE
  t        text;
  tabelas  text[] := ARRAY[
    'clientes', 'conciliacoes', 'transacoes', 'apuracao_cbs_ibs',
    -- Tabelas fiscais + disposição (org_id adicionado na migration 020).
    'documento_fiscal', 'cruzamento_fiscal', 'conformidade_fornecedor',
    'guia_tributo', 'contrato', 'carta_versao', 'transacao_disposicao',
    -- Fila de jobs assíncronos (migration 023) — tem AINDA a policy adicional
    -- worker_access (criada na migration/abaixo), p/ o loop do worker.
    'jobs',
    -- Trilha de auditoria (migration 024 add org_id). A cadeia de hash é por org.
    -- ⚠️ Eventos de SISTEMA (org_id NULL — login pré-contexto, alertas internos)
    -- ficam fora desta policy (NULL = NULL ≡ falso no Postgres): sob app_orgconc
    -- só seriam graváveis com uma policy adicional para org_id IS NULL. Hoje a
    -- conexão é `postgres` (BYPASSRLS), então isto é inerte; reavaliar no cutover.
    'audit_events'
  ];
BEGIN
  FOREACH t IN ARRAY tabelas LOOP
    IF to_regclass('public.' || t) IS NULL THEN
      RAISE NOTICE 'RLS: tabela public.% ausente — pulando', t;
      CONTINUE;
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = t AND column_name = 'org_id'
    ) THEN
      RAISE NOTICE 'RLS: public.% sem coluna org_id — pulando', t;
      CONTINUE;
    END IF;

    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE public.%I FORCE  ROW LEVEL SECURITY', t);

    -- org_id nasce com a org do contexto da sessão quando o INSERT a omite.
    EXECUTE format(
      'ALTER TABLE public.%I ALTER COLUMN org_id '
      'SET DEFAULT NULLIF(current_setting(''app.org_id'', true), '''')::uuid', t);

    -- Substitui qualquer policy anterior (inclusive allow_all) pelo isolamento real.
    EXECUTE format('DROP POLICY IF EXISTS allow_all     ON public.%I', t);
    EXECUTE format('DROP POLICY IF EXISTS org_isolation ON public.%I', t);
    -- Policies legadas de uma tentativa antiga de RLS nativa do Supabase Auth
    -- (role `authenticated`, USING org_id = auth.jwt()->>'org_id'). Inertes para o
    -- backend (que conecta como app_orgconc, fora do role authenticated), mas drift
    -- do modelo declarado — removidas aqui para manter banco↔script alinhados.
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_org_policy', t);
    EXECUTE format(
      'CREATE POLICY org_isolation ON public.%I FOR ALL '
      'USING      (org_id = NULLIF(current_setting(''app.org_id'', true), '''')::uuid) '
      'WITH CHECK (org_id = NULLIF(current_setting(''app.org_id'', true), '''')::uuid)',
      t);

    -- Superadmin (leitura cross-org): policy SEPARADA e só FOR SELECT. Permissiva
    -- (OR com a org_isolation) → superadmin LÊ todas as orgs; como NÃO cobre
    -- INSERT/UPDATE/DELETE, escrita cross-org continua barrada pela org_isolation
    -- (leitura-só estrutural). Inerte sem `app.superadmin='on'` (fail-closed).
    EXECUTE format('DROP POLICY IF EXISTS superadmin_read ON public.%I', t);
    EXECUTE format(
      'CREATE POLICY superadmin_read ON public.%I FOR SELECT '
      'USING (current_setting(''app.superadmin'', true) = ''on'')',
      t);

    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO app_orgconc', t);
  END LOOP;
END $$;

-- 3. Fila de jobs (P1 #9): o LOOP do worker precisa claimar/finalizar jobs de
--    qualquer org. Policy permissiva via GUC app.worker — setado apenas por
--    api/services/job_queue (nunca em request). Inerte sem o GUC (fail-closed).
DO $$
BEGIN
  IF to_regclass('public.jobs') IS NOT NULL THEN
    DROP POLICY IF EXISTS worker_access ON public.jobs;
    CREATE POLICY worker_access ON public.jobs FOR ALL
      USING      (current_setting('app.worker', true) = 'on')
      WITH CHECK (current_setting('app.worker', true) = 'on');
  END IF;
END $$;
