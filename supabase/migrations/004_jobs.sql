-- OrgConc -- Tabela jobs (item 13: fila Arq)
-- IDEMPOTENTE.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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
