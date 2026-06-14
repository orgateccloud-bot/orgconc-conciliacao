# Schema do Banco de Dados — OrgConc Conciliação

**Projeto Supabase:** `cmnbmckwvkfexfkegxsf`
**URL:** `https://cmnbmckwvkfexfkegxsf.supabase.co`
**Região:** South America (São Paulo) 🇧🇷
**Última atualização:** 2026-06-01
**Migration head:** `010_usage_cost_tracking`

> ⚠️ **Fonte de verdade:** `api/db/models.py` + `migrations/versions/` (Alembic).
> Este documento é gerado a partir dos models. Divergências → confie no código.

---

## Histórico de Migrations

| Rev | Arquivo | O que faz |
|-----|---------|-----------|
| 001 | baseline | Baseline pós-SQL inicial Supabase |
| 002 | drop_orphan_tables | Remove `ml_predicoes` e `fsrs_memorias` |
| 003 | audit_events | Tabela `audit_events` com hash chain |
| 004 | conciliacoes_latency | Coluna `usage_latency_ms` em `conciliacoes` |
| 005 | ai_insights_cache | Tabela `ai_insights_cache` |
| 006 | fiscal_integration | `documento_fiscal`, `cruzamento_fiscal`, `conformidade_fornecedor`, `carta_versao` |
| 007 | orgs_guias_contratos | `orgs`, `llm_cost_daily`, `guia_tributo`, `contrato`, `transacao_disposicao` + coluna `org_id` |
| 008 | refresh_tokens | Tabela `refresh_tokens` |
| 009 | reconciliar_schema | Reconcilia drift Alembic/Supabase (idempotente) |
| 010 | usage_cost_tracking | Colunas `usage_input_tokens`, `usage_output_tokens`, `usage_cost_usd` em `conciliacoes` |

Para provisionar novo ambiente: `alembic upgrade head`

---

## Tabelas

### `orgs`
Tenant raiz (multi-tenancy futuro). FK alvo de `org_id` em clientes/conciliacoes/transacoes.

| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| nome | text | NO | — |
| plano | varchar(20) | YES | 'basico' |
| cnpj | text | YES | — |
| ativo | boolean | YES | true |
| criado_em | timestamptz | YES | now() |
| atualizado_em | timestamptz | YES | now() |

---

### `clientes`
Clientes do escritório contábil.

| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| org_id | uuid | YES | — *(FK orgs.id)* |
| nome | text | NO | — |
| cnpj | varchar(18) | YES | — *(UNIQUE)* |
| email | text | YES | — |
| telefone | text | YES | — |
| plano | varchar(20) | NO | 'basico' |
| ativo | boolean | NO | true |
| criado_em | timestamptz | NO | now() |
| atualizado_em | timestamptz | NO | now() |

**Índices:** `idx_clientes_org (org_id)`

---

### `conciliacoes`
Registro de cada operação de conciliação bancária.

| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| org_id | uuid | YES | — *(FK orgs.id)* |
| cliente_id | uuid | YES | — *(FK clientes.id)* |
| report_id | text | NO | — *(UNIQUE)* |
| modo | varchar(20) | NO | — *('llm'\|'simulacao_local'\|'multi_modelo'\|'llm_csv')* |
| total_transacoes | integer | YES | 0 |
| total_anomalias | integer | YES | 0 |
| valor_total_credito | numeric(15,2) | YES | — |
| valor_total_debito | numeric(15,2) | YES | — |
| periodo_inicio | date | YES | — |
| periodo_fim | date | YES | — |
| criado_em | timestamptz | NO | now() |
| usage_latency_ms | integer | YES | — |
| usage_input_tokens | integer | YES | — |
| usage_output_tokens | integer | YES | — |
| usage_cost_usd | numeric(10,6) | YES | — |

**Índices:** `idx_conciliacoes_cliente`, `idx_conciliacoes_criado_em`, `idx_conciliacoes_org`

---

### `transacoes`
Transações individuais extraídas dos arquivos OFX/CSV/XML.

| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| org_id | uuid | YES | — *(FK orgs.id)* |
| conciliacao_id | uuid | YES | — *(FK conciliacoes.id CASCADE)* |
| cliente_id | uuid | YES | — *(FK clientes.id)* |
| data_lancamento | date | NO | — |
| valor | numeric(15,2) | NO | — |
| memo | text | YES | — |
| categoria | text | YES | — |
| banco | text | YES | — |
| tipo | text | YES | — *(PIX/TED/Cartão/Folha…)* |
| eh_anomalia | boolean | NO | false |
| criado_em | timestamptz | NO | now() |

**Índices:** `idx_transacoes_conciliacao`, `idx_transacoes_cliente`, `idx_transacoes_data`, `idx_transacoes_org`, `idx_transacoes_eh_anomalia (WHERE eh_anomalia = true)`

---

### `audit_events`
Log imutável com hash chain (SHA-256). Registra ações de usuários.

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| ts | timestamptz | NO |
| actor_email | text | YES |
| actor_sub | text | YES |
| action | text | NO |
| resource_type | text | YES |
| resource_id | text | YES |
| payload | jsonb | YES |
| payload_hash | varchar(64) | NO |
| prev_hash | varchar(64) | NO |
| request_id | varchar(32) | YES |

---

### `ai_insights_cache`
Cache de insights gerados por IA por usuário/período (TTL-based).

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| actor_sub | text | NO |
| periodo_dias | integer | NO |
| gerado_em | timestamptz | NO |
| expira_em | timestamptz | NO |
| payload | jsonb | NO |

---

### `llm_cost_daily`
Custo Claude API acumulado por dia (UTC). UPSERT incremental por delta.

| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| dia | date | NO | — *(UNIQUE)* |
| custo_usd | numeric(10,4) | NO | 0 |
| chamadas | integer | NO | 0 |
| atualizado_em | timestamptz | YES | now() |

**Índice:** `ix_llm_cost_daily_dia (dia) UNIQUE`

---

### `refresh_tokens`
Refresh tokens opacos (sha256) — rotação com revogação server-side.

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| sub | text | NO |
| token_hash | varchar(64) | NO *(UNIQUE)* |
| emitido_em | timestamptz | NO |
| expira_em | timestamptz | NO |
| revogado_em | timestamptz | YES |
| substituido_por | uuid | YES *(FK self)* |
| ip | text | YES |
| user_agent | text | YES |

---

### `guia_tributo`
Guias tributárias (DARF, DAS, GPS, GNRE) — matcher estágio 4.

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| cliente_id | uuid | NO *(FK clientes.id CASCADE)* |
| tipo | text | NO *(DARF/DAS/GPS/GNRE)* |
| codigo_receita | text | YES |
| valor | numeric(15,2) | NO |
| competencia | text | YES *(AAAA-MM)* |
| data_vencimento | date | YES |
| conta_contabil | text | YES |
| ativo | boolean | YES |
| criado_em | timestamptz | YES |

---

### `contrato`
Contratos recorrentes (aluguel, leasing, seguro) — matcher estágio 5.

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| cliente_id | uuid | NO *(FK clientes.id CASCADE)* |
| descricao | text | NO |
| valor | numeric(15,2) | NO |
| periodicidade | varchar(20) | YES |
| padrao_memo | text | YES |
| conta_contabil | text | YES |
| ativo | boolean | YES |
| criado_em | timestamptz | YES |

---

### `transacao_disposicao`
Disposição contábil por transação após cascata de matchers.

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| conciliacao_id | uuid | NO *(FK conciliacoes.id CASCADE)* |
| transacao_idx | integer | NO |
| estagio | integer | NO |
| disposicao | text | NO |
| contraparte | text | YES |
| conta_contabil | text | YES |
| origem | text | YES |
| flag | text | YES |
| nfe_chave | varchar(44) | YES |
| criado_em | timestamptz | YES |

---

### `documento_fiscal`
NF-e (mod 55), CT-e (mod 57), NFS-e após parsing SEFAZ.

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| cliente_id | uuid | NO *(FK clientes.id CASCADE)* |
| tipo | varchar(10) | NO *('NF-e'\|'CT-e'\|'NFS-e')* |
| modelo | varchar(3) | NO *('55'\|'57'\|'65')* |
| chave | varchar(44) | NO |
| numero / serie | text | YES |
| data_emissao | date | YES |
| emit_cnpj / emit_nome / emit_uf | text | YES |
| dest_cnpj / dest_nome | text | YES |
| valor_total / valor_icms / valor_pis / valor_cofins / valor_iss | numeric(15,2) | — |
| natureza_operacao | text | YES |
| xml_path | text | YES |
| criado_em | timestamptz | YES |

**Índices:** `ix_docfiscal_cliente_chave (UNIQUE)`, `ix_docfiscal_cliente_emit`, `ix_docfiscal_cliente_data`

---

### `cruzamento_fiscal`
Resultado do cruzamento documento fiscal × transação OFX.

Status: `CASADO` | `VALOR_DIVERGENTE` | `SEM_PAGAMENTO` | `SEM_NF`

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| cliente_id | uuid | NO |
| documento_id | uuid | YES *(FK documento_fiscal)* |
| transacao_id | uuid | YES *(FK transacoes)* |
| status | varchar(20) | NO |
| diferenca_valor | numeric(15,2) | YES |
| diferenca_dias | integer | YES |
| criado_em | timestamptz | YES |

---

### `carta_versao`
Versões da Carta de Constatação por cliente (audit trail de emissão).

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| cliente_id | uuid | NO *(FK clientes.id CASCADE)* |
| versao | varchar(50) | NO |
| risco_total | numeric(15,2) | NO |
| total_fornecedores | integer | NO |
| payload_hash | varchar(64) | NO |
| markdown | text | YES |
| gerado_em | timestamptz | NO |

---

### `conformidade_fornecedor`
Score de conformidade fiscal por fornecedor (CNPJ) × cliente.

Classe de risco: `BAIXO` | `MEDIO` | `ALTO` | `CRITICO`

| Coluna | Tipo | Nullable |
|--------|------|----------|
| id | uuid | NO |
| cliente_id | uuid | NO *(FK clientes.id CASCADE)* |
| cnpj_fornecedor | varchar(14) | NO |
| razao_social | text | YES |
| periodo_inicio / periodo_fim | date | YES |
| volume_pago / volume_nf | numeric(15,2) | NO |
| conformidade_pct | numeric(5,2) | NO |
| n_pagamentos / n_nfes | integer | NO |
| risco_classe | varchar(10) | NO |
| risco_tributario_anual | numeric(15,2) | NO |
| flags | text | YES *(CSV: REDE_FROTA_TYPE,MEI_SEM_CTE…)* |
| atualizado_em | timestamptz | NO |

**Índices:** `ix_conformidade_cliente_cnpj (UNIQUE)`, `ix_conformidade_cliente_risco`

---

## Tabelas removidas (históricas)

| Tabela | Removida em | Motivo |
|--------|-------------|--------|
| `ml_predicoes` | Migration 002 | Feature abandonada |
| `fsrs_memorias` | Migration 002 | Feature abandonada |

---

## Row Level Security (RLS)

**RLS real por `org_id` está ATIVO e enforçado em produção** (desde 2026-06-07):
o backend conecta como `app_orgconc` (NOBYPASSRLS) e as tabelas de negócio têm
FORCE RLS + policy `org_isolation` (GUC `app.org_id` via `SET LOCAL`).

> ⚠️ **NÃO copie policies deste documento.** A fonte de verdade das policies é
> versionada em [`db/rls/`](db/rls/) — `org_isolation.sql` (tabelas de negócio),
> `contraparte_org_isolation.sql`, `infra_allow_all.sql` (tabelas sem tenant) e
> `rollout_grants.sql` (role/grants). Policies permissivas (`USING (true)`)
> em tabelas de negócio anulam o isolamento multi-tenant — provisione ambientes
> novos executando os scripts de `db/rls/`, nunca SQL ad-hoc copiado de docs.

---

## Provisionamento de novo ambiente

```bash
# 1. Configure DATABASE_URL no .env (Supabase pooler porta 6543)
# 2. Aplique todas as migrations
alembic upgrade head

# 3. Verifique que não há drift
alembic check
```

**Não rodar** os arquivos `supabase/migrations/*.sql` diretamente em bancos que já passaram pelas migrations Alembic — são scripts de bootstrap histórico.
