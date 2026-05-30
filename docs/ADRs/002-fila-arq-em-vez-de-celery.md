# ADR-002: Arq como fila assíncrona (em vez de Celery)

- **Status:** Aceito
- **Data:** 2026-05-25

## Contexto

`POST /conciliar/ofx` em modo LLM bloqueia o worker HTTP até 90 s. Para escalar precisamos de fila assíncrona.

Opções:
- **Celery** (canonical no Python).
- **RQ** (mais simples, mas síncrono).
- **Arq** (async-native, leve, Redis).
- **Dramatiq** (alternativa async).

## Decisão

**Arq** (`arq==0.27`).

## Justificativa

- API já é toda `async def` (FastAPI + asyncpg). Arq é async-native, sem ponte sync/async.
- Sem broker novo: Redis já entra para rate-limit distribuído (Item 3). Reuso.
- Footprint baixo: 1 dep, sem celery-beat, sem flower.
- Suficiente para nossa escala atual (< 100 jobs/dia).

## Consequências

**Positivas:**
- Worker `arq api.workers.WorkerSettings` rodando ao lado da API.
- Endpoints `/v1/jobs` + tabela `jobs` para tracking.
- LLM em background; cliente faz polling em `GET /v1/jobs/{id}`.

**Negativas:**
- Comunidade menor que Celery (menos plugins, menos tutoriais).
- Sem retry sofisticado pronto (rolar manualmente em `tasks.py`).

## Quando migrar para Celery

- Volume > 1k jobs/dia
- Necessidade de scheduled tasks (celery-beat)
- Múltiplos brokers (RabbitMQ + Redis)
- Time grande precisa de UI rica (Flower)
