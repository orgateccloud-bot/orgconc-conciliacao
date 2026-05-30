-- OrgConc -- audit_log (item 17)
-- IDEMPOTENTE.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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
