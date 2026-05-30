-- OrgConc -- Multi-tenancy (item 16)
-- IDEMPOTENTE. Multi-step seguro:
--   1) Cria tabela orgs
--   2) Insere org "default" e captura UUID
--   3) Adiciona org_id NULL em clientes/conciliacoes/transacoes/jobs
--   4) Backfill para org default
--   5) NOT NULL
--   6) RLS habilitado mas com policy permissiva (configurar depois)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── 1. Tabela orgs ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orgs (
  id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  nome          TEXT         NOT NULL,
  plano         TEXT         NOT NULL DEFAULT 'basico'
                CHECK (plano IN ('basico','pro','enterprise')),
  cnpj          TEXT         UNIQUE,
  ativo         BOOLEAN      NOT NULL DEFAULT true,
  criado_em     TIMESTAMPTZ  NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ── 2. Org default (se ainda nao existe) ───────────────────────────────────
INSERT INTO orgs (id, nome, plano)
SELECT '00000000-0000-0000-0000-000000000001'::uuid, 'ORGATEC (default)', 'enterprise'
WHERE NOT EXISTS (
  SELECT 1 FROM orgs WHERE id = '00000000-0000-0000-0000-000000000001'::uuid
);

-- ── 3. Adiciona org_id (NULL) em cada tabela ───────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='clientes' AND column_name='org_id'
  ) THEN
    ALTER TABLE clientes ADD COLUMN org_id UUID REFERENCES orgs(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='conciliacoes' AND column_name='org_id'
  ) THEN
    ALTER TABLE conciliacoes ADD COLUMN org_id UUID REFERENCES orgs(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='transacoes' AND column_name='org_id'
  ) THEN
    ALTER TABLE transacoes ADD COLUMN org_id UUID REFERENCES orgs(id);
  END IF;

  -- jobs e adicionado se a tabela ja existir (migration 004)
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='jobs') THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name='jobs' AND column_name='org_id'
    ) THEN
      ALTER TABLE jobs ADD COLUMN org_id UUID REFERENCES orgs(id);
    END IF;
  END IF;
END;
$$;

-- ── 4. Backfill: tudo que esta NULL vira org default ───────────────────────
UPDATE clientes      SET org_id = '00000000-0000-0000-0000-000000000001'::uuid WHERE org_id IS NULL;
UPDATE conciliacoes  SET org_id = '00000000-0000-0000-0000-000000000001'::uuid WHERE org_id IS NULL;
UPDATE transacoes    SET org_id = '00000000-0000-0000-0000-000000000001'::uuid WHERE org_id IS NULL;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='jobs') THEN
    UPDATE jobs SET org_id = '00000000-0000-0000-0000-000000000001'::uuid WHERE org_id IS NULL;
  END IF;
END;
$$;

-- ── 5. NOT NULL (so apos backfill garantido) ───────────────────────────────
ALTER TABLE clientes     ALTER COLUMN org_id SET NOT NULL;
ALTER TABLE conciliacoes ALTER COLUMN org_id SET NOT NULL;
ALTER TABLE transacoes   ALTER COLUMN org_id SET NOT NULL;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='jobs' AND column_name='org_id')
  THEN
    -- Pode ainda nao estar populado em ambientes sem dados de jobs ainda — torna NOT NULL depois manualmente.
    BEGIN
      ALTER TABLE jobs ALTER COLUMN org_id SET NOT NULL;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE '005: jobs.org_id ainda nao pode ser NOT NULL (talvez sem dados). Faca manualmente quando seguro.';
    END;
  END IF;
END;
$$;

-- ── 6. Indices ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_clientes_org      ON clientes(org_id);
CREATE INDEX IF NOT EXISTS idx_conciliacoes_org  ON conciliacoes(org_id);
CREATE INDEX IF NOT EXISTS idx_transacoes_org    ON transacoes(org_id);

-- ── 7. RLS placeholder (sera configurado em PR separado) ───────────────────
-- ALTER TABLE clientes     ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE conciliacoes ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE transacoes   ENABLE ROW LEVEL SECURITY;
-- (Policies dependem de JWT claim org_id — definidas no app, nao no SQL.
--  Por enquanto deixar RLS desligado; ativar somente quando policies tiverem
--  cobertura E2E.)
