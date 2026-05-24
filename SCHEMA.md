# Schema do Banco de Dados - Orgconc Conciliação

**Projeto Supabase:** `cmnbmckwvkfexfkegxsf`
**URL:** `https://cmnbmckwvkfexfkegxsf.supabase.co`
**Região:** South America (São Paulo) 🇧🇷
**Última verificação:** 2026-05-24

---

## Tabelas

### `clientes`
| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| nome | text | NO | NULL |
| cnpj | text | YES | NULL |
| email | text | YES | NULL |
| telefone | text | YES | NULL |
| plano | text | NO | 'basico' |
| ativo | boolean | NO | true |
| criado_em | timestamptz | NO | now() |
| atualizado_em | timestamptz | NO | now() |

### `conciliacoes`
| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| cliente_id | uuid | YES | NULL |
| report_id | text | NO | NULL |
| total_anomalias | integer | NO | 0 |
| valor_total_credito | numeric | YES | NULL |
| valor_total_debito | numeric | YES | NULL |
| periodo_inicio | date | YES | NULL |
| periodo_fim | date | YES | NULL |
| criado_em | timestamptz | NO | now() |

### `transacoes`
| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| conciliacao_id | uuid | YES | NULL |
| cliente_id | uuid | YES | NULL |
| data_lancamento | date | NO | NULL |
| ... (demais colunas) | | | |

### `fsrs_memorias`
| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| ... (demais colunas) | | | |

### `ml_predicoes`
| Coluna | Tipo | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| confirmado_por | text | YES | NULL |
| correto | boolean | YES | NULL |
| criado_em | timestamptz | NO | now() |

---

## Row Level Security (RLS)

RLS está **ATIVADO** em todas as tabelas. As seguintes políticas foram configuradas para uso interno:

| Tabela | Política | Comando | Aplicado a |
|--------|----------|---------|-----------|
| clientes | allow_all_clientes | ALL | public |
| conciliacoes | allow_all_conciliacoes | ALL | public |
| transacoes | allow_all_transacoes | ALL | public |
| fsrs_memorias | allow_all_fsrs_memorias | ALL | public |
| ml_predicoes | allow_all_ml_predicoes | ALL | public |

> **Nota:** Políticas permitem acesso total via `anon` key para uso interno.
> Para produção pública, restrinja as políticas por `auth.uid()`.

---

## SQL das Políticas RLS

```sql
-- Políticas para uso interno (acesso total)
CREATE POLICY "allow_all_clientes" ON public.clientes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_conciliacoes" ON public.conciliacoes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_transacoes" ON public.transacoes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_fsrs_memorias" ON public.fsrs_memorias FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_ml_predicoes" ON public.ml_predicoes FOR ALL USING (true) WITH CHECK (true);
```

---

## Teste de Persistência

✅ **INSERT testado e confirmado em 2026-05-24:**
- Inserção via REST API com anon key: `HTTP 201 Created`
- Retorno com UUID gerado, timestamps automáticos
- DELETE de limpeza: `HTTP 204 No Content`

---

## Configuração do .env

```env
SUPABASE_URL=https://cmnbmckwvkfexfkegxsf.supabase.co
SUPABASE_ANON_KEY=<copiar de Settings > API Keys > Legacy > anon>
SUPABASE_SERVICE_ROLE_KEY=<copiar de Settings > API Keys > Legacy > service_role>
```

Obter as keys em:
`https://supabase.com/dashboard/project/cmnbmckwvkfexfkegxsf/settings/api-keys/legacy`
