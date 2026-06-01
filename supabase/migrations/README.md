# Migrations Supabase — Nota sobre estratégia

## TL;DR

**Alembic é o dono das migrations.** Os arquivos `.sql` nesta pasta são
scripts de **bootstrap histórico** — usados uma única vez para criar o schema
inicial no Supabase. Não os reexecute em bancos já migrados.

---

## Como provisionar um novo ambiente

```bash
# 1. Configure DATABASE_URL no .env apontando para o Supabase pooler (porta 6543)
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<SENHA>@aws-1-sa-east-1.pooler.supabase.com:6543/postgres

# 2. Aplique todas as migrations Alembic
alembic upgrade head

# 3. Confirme que não há drift
alembic check
```

As migrations Alembic estão em `migrations/versions/` (010 revisões).
O schema completo e atualizado está documentado em `SCHEMA.md` na raiz do projeto.

---

## Arquivos nesta pasta

| Arquivo | Status | Conteúdo |
|---------|--------|----------|
| `001_schema_inicial.sql` | Histórico | Schema original: `clientes`, `conciliacoes`, `transacoes`, `ml_predicoes`, `fsrs_memorias` |
| `002_fix_uuid_types.sql` | Histórico | Correção idempotente de tipos UUID em ambiente legado |

> **Atenção:** `001_schema_inicial.sql` define tabelas (`ml_predicoes`, `fsrs_memorias`)
> que foram **removidas** pela migration Alembic 002. O schema atual tem 15 tabelas
> que não estão representadas aqui. Consulte `SCHEMA.md` para o estado atual.

---

## Linha do tempo

```
2026-05-XX  001_schema_inicial.sql executado no Supabase (bootstrap manual)
2026-05-XX  002_fix_uuid_types.sql executado (correção UUID)
2026-05-25  Alembic assume controle — migrations 001 a 006
2026-05-31  Migrations 007 a 009 (orgs, refresh_tokens, reconciliação)
2026-06-01  Migration 010 (custo LLM por conciliação)
```
