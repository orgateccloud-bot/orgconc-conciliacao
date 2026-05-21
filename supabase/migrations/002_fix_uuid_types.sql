-- OrgConc -- Correc̃ao de tipos UUID em ambientes com schema legado (INTEGER PKs)
-- Executa no Supabase: SQL Editor -> New Query -> Cole e rode
-- IDEMPOTENTE: verifica o tipo atual antes de alterar.

DO $$
DECLARE
  v_id_type TEXT;
BEGIN
  SELECT data_type INTO v_id_type
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name   = 'clientes'
    AND column_name  = 'id';

  IF v_id_type IS NULL THEN
    RAISE NOTICE '002_fix_uuid_types: tabela clientes nao existe -- nada a fazer.';
    RETURN;
  END IF;

  IF v_id_type = 'uuid' THEN
    RAISE NOTICE '002_fix_uuid_types: clientes.id ja e UUID -- nenhuma alteracao necessaria.';
    RETURN;
  END IF;

  RAISE NOTICE '002_fix_uuid_types: clientes.id e % -- recriando tabelas com UUID...', v_id_type;

  DROP TABLE IF EXISTS fsrs_memorias   CASCADE;
  DROP TABLE IF EXISTS ml_predicoes    CASCADE;
  DROP TABLE IF EXISTS transacoes      CASCADE;
  DROP TABLE IF EXISTS conciliacoes    CASCADE;
  DROP TABLE IF EXISTS clientes        CASCADE;

  RAISE NOTICE '002_fix_uuid_types: tabelas legadas removidas. Recriando...';

  CREATE TABLE clientes (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nome          TEXT        NOT NULL,
    cnpj          TEXT        UNIQUE,
    email         TEXT,
    telefone      TEXT,
    plano         TEXT        NOT NULL DEFAULT 'basico'
                              CHECK (plano IN ('basico', 'pro', 'enterprise')),
    ativo         BOOLEAN     NOT NULL DEFAULT true,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  CREATE TABLE conciliacoes (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id          UUID        REFERENCES clientes(id) ON DELETE SET NULL,
    report_id           TEXT        UNIQUE NOT NULL,
    modo                TEXT        NOT NULL CHECK (modo IN ('llm', 'simulacao', 'simulacao_local', 'multi_modelo')),
    total_transacoes    INT         NOT NULL DEFAULT 0,
    total_anomalias     INT         NOT NULL DEFAULT 0,
    valor_total_credito NUMERIC(15,2),
    valor_total_debito  NUMERIC(15,2),
    periodo_inicio      DATE,
    periodo_fim         DATE,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  CREATE TABLE transacoes (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conciliacao_id   UUID        REFERENCES conciliacoes(id) ON DELETE CASCADE,
    cliente_id       UUID        REFERENCES clientes(id) ON DELETE SET NULL,
    data_lancamento  DATE        NOT NULL,
    valor            NUMERIC(15,2) NOT NULL,
    memo             TEXT,
    categoria        TEXT,
    banco            TEXT,
    tipo             TEXT,
    eh_anomalia      BOOLEAN     NOT NULL DEFAULT false,
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  CREATE TABLE ml_predicoes (
    id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    transacao_id   UUID    REFERENCES transacoes(id) ON DELETE CASCADE,
    modelo         TEXT    NOT NULL,
    predicao       TEXT    NOT NULL,
    confianca      FLOAT   NOT NULL CHECK (confianca BETWEEN 0 AND 1),
    confirmado_por TEXT,
    correto        BOOLEAN,
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  CREATE TABLE fsrs_memorias (
    id               UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id       UUID    REFERENCES clientes(id) ON DELETE CASCADE,
    pattern_key      TEXT    NOT NULL,
    pattern_exemplo  TEXT,
    categoria        TEXT    NOT NULL,
    estabilidade     FLOAT   NOT NULL DEFAULT 1.0,
    dificuldade      FLOAT   NOT NULL DEFAULT 0.3,
    proxima_revisao  DATE    NOT NULL DEFAULT CURRENT_DATE + 1,
    repeticoes       INT     NOT NULL DEFAULT 0,
    lapsos           INT     NOT NULL DEFAULT 0,
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cliente_id, pattern_key)
  );

  CREATE INDEX IF NOT EXISTS idx_conciliacoes_cliente     ON conciliacoes(cliente_id);
  CREATE INDEX IF NOT EXISTS idx_transacoes_conciliacao   ON transacoes(conciliacao_id);
  CREATE INDEX IF NOT EXISTS idx_transacoes_cliente       ON transacoes(cliente_id);
  CREATE INDEX IF NOT EXISTS idx_transacoes_data          ON transacoes(data_lancamento);
  CREATE INDEX IF NOT EXISTS idx_ml_predicoes_transacao   ON ml_predicoes(transacao_id);
  CREATE INDEX IF NOT EXISTS idx_fsrs_cliente_revisao     ON fsrs_memorias(cliente_id, proxima_revisao);
  CREATE INDEX IF NOT EXISTS idx_transacoes_eh_anomalia   ON transacoes(eh_anomalia) WHERE eh_anomalia = true;
  CREATE INDEX IF NOT EXISTS idx_clientes_atualizado_em   ON clientes(atualizado_em);
  CREATE INDEX IF NOT EXISTS idx_conciliacoes_criado_em   ON conciliacoes(criado_em);

  CREATE OR REPLACE FUNCTION set_atualizado_em()
  RETURNS TRIGGER LANGUAGE plpgsql AS $func$
  BEGIN NEW.atualizado_em = now(); RETURN NEW; END;
  $func$;

  CREATE OR REPLACE TRIGGER trg_clientes_atualizado_em
  BEFORE UPDATE ON clientes
  FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();

  CREATE OR REPLACE TRIGGER trg_fsrs_atualizado_em
  BEFORE UPDATE ON fsrs_memorias
  FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();

  RAISE NOTICE '002_fix_uuid_types: schema UUID recriado com sucesso.';
END;
$$;
