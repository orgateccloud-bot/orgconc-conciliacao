-- =====================================================================
-- OrgConc — Aplicar migrations 005, 006 e 007 (acumulado)
-- =====================================================================
-- TODAS as queries abaixo sao IDEMPOTENTES:
--   - usam IF NOT EXISTS / DO $$ ... $$ com checagem
--   - rodar 2x nao causa dano
--   - reverter requer rollback manual (DROP TABLE), nao ha downgrade automatico
--
-- COMO APLICAR:
--   1. Supabase Dashboard > SQL Editor > New query
--   2. Cole TODO este arquivo
--   3. Run
--   4. Confirme as mensagens "NOTICE: ..." sem ERROR
--   5. (Opcional) Apos sucesso: alembic stamp 007  (marca como aplicada localmente)
--
-- POS-CONDICAO ESPERADA:
--   - SELECT COUNT(*) FROM orgs;         -- >= 1 (a default)
--   - SELECT column_name FROM information_schema.columns
--       WHERE table_name='clientes' AND column_name='org_id';  -- retorna 1 linha
--   - SELECT COUNT(*) FROM feature_flags;  -- >= 5
-- =====================================================================

-- ╔═══════════════════════════════════════════════════════════════════╗
-- ║  005 — orgs + multi-tenancy                                        ║
-- ╚═══════════════════════════════════════════════════════════════════╝
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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

INSERT INTO orgs (id, nome, plano)
SELECT '00000000-0000-0000-0000-000000000001'::uuid, 'ORGATEC (default)', 'enterprise'
WHERE NOT EXISTS (
  SELECT 1 FROM orgs WHERE id = '00000000-0000-0000-0000-000000000001'::uuid
);

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

ALTER TABLE clientes     ALTER COLUMN org_id SET NOT NULL;
ALTER TABLE conciliacoes ALTER COLUMN org_id SET NOT NULL;
ALTER TABLE transacoes   ALTER COLUMN org_id SET NOT NULL;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='jobs' AND column_name='org_id')
  THEN
    BEGIN
      ALTER TABLE jobs ALTER COLUMN org_id SET NOT NULL;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE '005: jobs.org_id nao pode virar NOT NULL ainda (sem dados ou tabela ausente).';
    END;
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_clientes_org      ON clientes(org_id);
CREATE INDEX IF NOT EXISTS idx_conciliacoes_org  ON conciliacoes(org_id);
CREATE INDEX IF NOT EXISTS idx_transacoes_org    ON transacoes(org_id);


-- ╔═══════════════════════════════════════════════════════════════════╗
-- ║  Pre-requisito para 006 e 007: tabela jobs (vem da 004)            ║
-- ║  Se voce nunca rodou 004, criamos aqui (idempotente).              ║
-- ╚═══════════════════════════════════════════════════════════════════╝
CREATE TABLE IF NOT EXISTS jobs (
  id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  sub           TEXT         NOT NULL,
  tipo          VARCHAR(40)  NOT NULL,
  status        VARCHAR(20)  NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','running','done','failed','cancelled')),
  input_json    TEXT,
  output_json   TEXT,
  erro          TEXT,
  progresso     INT          NOT NULL DEFAULT 0,
  criado_em     TIMESTAMPTZ  NOT NULL DEFAULT now(),
  iniciado_em   TIMESTAMPTZ,
  finalizado_em TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_jobs_sub    ON jobs(sub);
CREATE INDEX IF NOT EXISTS idx_jobs_tipo   ON jobs(tipo);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
-- e adiciona org_id em jobs se foi criada agora
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='jobs' AND column_name='org_id'
  ) THEN
    ALTER TABLE jobs ADD COLUMN org_id UUID REFERENCES orgs(id);
    UPDATE jobs SET org_id = '00000000-0000-0000-0000-000000000001'::uuid WHERE org_id IS NULL;
    ALTER TABLE jobs ALTER COLUMN org_id SET NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_jobs_org ON jobs(org_id);
  END IF;
END;
$$;


-- ╔═══════════════════════════════════════════════════════════════════╗
-- ║  Pre-requisito 003: tabela refresh_tokens                          ║
-- ╚═══════════════════════════════════════════════════════════════════╝
CREATE TABLE IF NOT EXISTS refresh_tokens (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  sub             TEXT        NOT NULL,
  token_hash      VARCHAR(64) NOT NULL UNIQUE,
  emitido_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
  expira_em       TIMESTAMPTZ NOT NULL,
  revogado_em     TIMESTAMPTZ,
  substituido_por UUID        REFERENCES refresh_tokens(id),
  ip              TEXT,
  user_agent      TEXT
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_sub_ativo
  ON refresh_tokens(sub) WHERE revogado_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expira ON refresh_tokens(expira_em);


-- ╔═══════════════════════════════════════════════════════════════════╗
-- ║  006 — audit_log                                                   ║
-- ╚═══════════════════════════════════════════════════════════════════╝
CREATE TABLE IF NOT EXISTS audit_log (
  id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       UUID         NOT NULL REFERENCES orgs(id),
  usuario_sub  TEXT         NOT NULL,
  acao         VARCHAR(20)  NOT NULL,
  entidade     VARCHAR(60)  NOT NULL,
  entidade_id  VARCHAR(80),
  payload_hash VARCHAR(64),
  ip           TEXT,
  user_agent   TEXT,
  status_code  INT          NOT NULL,
  request_id   VARCHAR(32),
  criado_em    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_org_criado ON audit_log(org_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_audit_sub        ON audit_log(usuario_sub);
CREATE INDEX IF NOT EXISTS idx_audit_acao       ON audit_log(acao);


-- ╔═══════════════════════════════════════════════════════════════════╗
-- ║  007 — feature_flags                                               ║
-- ╚═══════════════════════════════════════════════════════════════════╝
CREATE TABLE IF NOT EXISTS feature_flags (
  key            TEXT         PRIMARY KEY,
  enabled        BOOLEAN      NOT NULL DEFAULT false,
  rollout_rules  JSONB        NOT NULL DEFAULT '{}'::jsonb,
  descricao      TEXT,
  atualizado_em  TIMESTAMPTZ  NOT NULL DEFAULT now(),
  atualizado_por TEXT
);

INSERT INTO feature_flags (key, enabled, descricao) VALUES
  ('conciliacao_multi_modelo',   true,  'Permite ?multi_modelo=true em /conciliar/ofx'),
  ('conciliacao_simular',        true,  'Permite ?simular=true em /conciliar/ofx'),
  ('serpro_consulta_cnpj',       false, 'Habilita /v1/serpro/cnpj (controla rollout)'),
  ('serpro_consulta_cpf',        false, 'Habilita /v1/serpro/cpf'),
  ('jobs_async_fila',            false, 'Roteia /conciliar/ofx via fila Arq em vez de sync')
ON CONFLICT (key) DO NOTHING;


-- ╔═══════════════════════════════════════════════════════════════════╗
-- ║  Validacao final                                                   ║
-- ╚═══════════════════════════════════════════════════════════════════╝
DO $$
DECLARE
  orgs_count INT;
  ff_count INT;
  cli_org INT;
BEGIN
  SELECT COUNT(*) INTO orgs_count FROM orgs;
  SELECT COUNT(*) INTO ff_count FROM feature_flags;
  SELECT COUNT(*) INTO cli_org FROM information_schema.columns
    WHERE table_name='clientes' AND column_name='org_id';
  RAISE NOTICE '────────────────────────────────────────';
  RAISE NOTICE 'OrgConc migrations 005-007 aplicadas:';
  RAISE NOTICE '  orgs:                %', orgs_count;
  RAISE NOTICE '  feature_flags:       %', ff_count;
  RAISE NOTICE '  clientes.org_id col: %', cli_org;
  RAISE NOTICE '────────────────────────────────────────';
END;
$$;
