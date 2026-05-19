-- OrgConc — Schema inicial
-- Executa no Supabase: SQL Editor → New Query → Cole e rode

-- ── Extensões ─────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── clientes ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clientes (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nome        TEXT        NOT NULL,
    cnpj        TEXT        UNIQUE,
    email       TEXT,
    telefone    TEXT,
    plano       TEXT        NOT NULL DEFAULT 'basico'
                            CHECK (plano IN ('basico', 'pro', 'enterprise')),
    ativo       BOOLEAN     NOT NULL DEFAULT true,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── conciliacoes ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conciliacoes (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id          UUID        REFERENCES clientes(id) ON DELETE SET NULL,
    report_id           TEXT        UNIQUE NOT NULL,   -- compatível com JSON atual
    modo                TEXT        NOT NULL CHECK (modo IN ('llm', 'simulacao')),
    total_transacoes    INT         NOT NULL DEFAULT 0,
    total_anomalias     INT         NOT NULL DEFAULT 0,
    valor_total_credito NUMERIC(15,2),
    valor_total_debito  NUMERIC(15,2),
    periodo_inicio      DATE,
    periodo_fim         DATE,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── transacoes ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transacoes (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conciliacao_id      UUID        REFERENCES conciliacoes(id) ON DELETE CASCADE,
    cliente_id          UUID        REFERENCES clientes(id) ON DELETE SET NULL,
    data_lancamento     DATE        NOT NULL,
    valor               NUMERIC(15,2) NOT NULL,
    memo                TEXT,
    categoria           TEXT,
    banco               TEXT,
    tipo                TEXT,       -- PIX, TED, Cartão, Folha, etc.
    eh_anomalia         BOOLEAN     NOT NULL DEFAULT false,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── ml_predicoes ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ml_predicoes (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    transacao_id    UUID        REFERENCES transacoes(id) ON DELETE CASCADE,
    modelo          TEXT        NOT NULL,   -- 'xgboost_v1', 'lstm_v1', 'heuristica'
    predicao        TEXT        NOT NULL,
    confianca       FLOAT       NOT NULL CHECK (confianca BETWEEN 0 AND 1),
    confirmado_por  TEXT,                   -- NULL = pendente, 'humano', 'auto'
    correto         BOOLEAN,                -- feedback do usuário
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── fsrs_memorias ─────────────────────────────────────────────────────────
-- Sistema de revisão espaçada: padrões que o modelo ainda não memorizou
CREATE TABLE IF NOT EXISTS fsrs_memorias (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id      UUID        REFERENCES clientes(id) ON DELETE CASCADE,
    pattern_key     TEXT        NOT NULL,   -- hash do padrão (memo normalizado)
    pattern_exemplo TEXT,                   -- texto original para exibir ao usuário
    categoria        TEXT        NOT NULL,
    estabilidade    FLOAT       NOT NULL DEFAULT 1.0,
    dificuldade     FLOAT       NOT NULL DEFAULT 0.3,
    proxima_revisao DATE        NOT NULL DEFAULT CURRENT_DATE + 1,
    repeticoes      INT         NOT NULL DEFAULT 0,
    lapsos          INT         NOT NULL DEFAULT 0,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cliente_id, pattern_key)
);

-- ── Índices ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_conciliacoes_cliente    ON conciliacoes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_transacoes_conciliacao  ON transacoes(conciliacao_id);
CREATE INDEX IF NOT EXISTS idx_transacoes_cliente      ON transacoes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_transacoes_data         ON transacoes(data_lancamento);
CREATE INDEX IF NOT EXISTS idx_ml_predicoes_transacao  ON ml_predicoes(transacao_id);
CREATE INDEX IF NOT EXISTS idx_fsrs_cliente_revisao    ON fsrs_memorias(cliente_id, proxima_revisao);

-- ── Trigger: atualiza atualizado_em automaticamente ───────────────────────
CREATE OR REPLACE FUNCTION set_atualizado_em()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.atualizado_em = now(); RETURN NEW; END;
$$;

CREATE OR REPLACE TRIGGER trg_clientes_atualizado_em
    BEFORE UPDATE ON clientes
    FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();

CREATE OR REPLACE TRIGGER trg_fsrs_atualizado_em
    BEFORE UPDATE ON fsrs_memorias
    FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();
