-- OrgConc -- Refresh tokens (item 4 do roadmap)
-- IDEMPOTENTE: usa IF NOT EXISTS / CHECK CONSTRAINT.
-- Tokens sao opacos: armazenamos apenas sha256(token).

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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
  ON refresh_tokens(sub)
  WHERE revogado_em IS NULL;

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expira
  ON refresh_tokens(expira_em);

-- Limpeza periodica recomendada (job cron):
--   DELETE FROM refresh_tokens WHERE expira_em < now() - INTERVAL '7 days';
