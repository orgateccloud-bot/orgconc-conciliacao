-- RLS REAL por organização (tenant = org_id) — PoC.
--
-- Substitui o padrão atual "allow_all" (USING (true)) por isolamento de verdade.
-- Aplicar no Supabase como owner (postgres). Em produção, o backend deve:
--   1. conectar com o role app_orgconc (NOBYPASSRLS) — NÃO com postgres;
--   2. executar `SET LOCAL app.org_id = '<uuid-da-org>'` no início de cada
--      transação, a partir do usuário autenticado.
--
-- Falha-FECHADA: sem app.org_id setado, current_setting(...,true) = NULL →
-- a comparação vira NULL (≡ falso) → zero linhas (nunca "tudo").
--
-- O teste tests/test_rls_isolation.py prova os 4 modos de falha contra um
-- Postgres real conectando como app_orgconc.

-- 1. Role da aplicação (NOBYPASSRLS): a RLS se aplica a ele.
--    Troque a senha no rollout (ALTER ROLE app_orgconc PASSWORD '...').
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_orgconc') THEN
    CREATE ROLE app_orgconc LOGIN PASSWORD 'CHANGE_ME_NO_ROLLOUT' NOBYPASSRLS;
  END IF;
END $$;

-- 2. Tabela tenant-scoped (PoC). org_id default = org do contexto da sessão.
CREATE TABLE IF NOT EXISTS public.contraparte (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id    uuid NOT NULL DEFAULT NULLIF(current_setting('app.org_id', true), '')::uuid,
  nome_real text NOT NULL,
  criado_em timestamptz NOT NULL DEFAULT now()
);

-- 3. RLS habilitada + FORCE (aplica até ao owner — defesa se algum dia o app for owner).
ALTER TABLE public.contraparte ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contraparte FORCE ROW LEVEL SECURITY;

-- 4. Política de isolamento por org. USING (leitura/update/delete) + WITH CHECK
--    (escrita). NULLIF(...,'') normaliza tanto NULL quanto '' (não setado) → NULL.
DROP POLICY IF EXISTS org_isolation ON public.contraparte;
CREATE POLICY org_isolation ON public.contraparte
  FOR ALL
  USING      (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
  WITH CHECK (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid);

-- 5. Privilégios mínimos ao role da aplicação (a RLS é que filtra as linhas).
GRANT USAGE ON SCHEMA public TO app_orgconc;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.contraparte TO app_orgconc;
