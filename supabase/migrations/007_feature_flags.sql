-- OrgConc -- feature_flags (item 26)
-- IDEMPOTENTE.

CREATE TABLE IF NOT EXISTS feature_flags (
  key            TEXT         PRIMARY KEY,
  enabled        BOOLEAN      NOT NULL DEFAULT false,
  rollout_rules  JSONB        NOT NULL DEFAULT '{}'::jsonb,
  descricao      TEXT,
  atualizado_em  TIMESTAMPTZ  NOT NULL DEFAULT now(),
  atualizado_por TEXT
);

-- Flags iniciais (idempotente)
INSERT INTO feature_flags (key, enabled, descricao)
VALUES
  ('conciliacao_multi_modelo',   true,  'Permite ?multi_modelo=true em /conciliar/ofx'),
  ('conciliacao_simular',        true,  'Permite ?simular=true em /conciliar/ofx'),
  ('serpro_consulta_cnpj',       false, 'Habilita /v1/serpro/cnpj (controla rollout)'),
  ('serpro_consulta_cpf',        false, 'Habilita /v1/serpro/cpf'),
  ('jobs_async_fila',            false, 'Roteia /conciliar/ofx via fila Arq em vez de sync')
ON CONFLICT (key) DO NOTHING;
