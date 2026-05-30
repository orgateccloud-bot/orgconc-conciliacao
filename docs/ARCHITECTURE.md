# Arquitetura — OrgConc

> Resumo executivo. Para o panorama completo (fluxogramas Mermaid, comparativo de camadas, roadmap), veja [`analise_camadas_arquitetura.md`](../analise_camadas_arquitetura.md) e [`projeto_implementacao_completo.md`](../projeto_implementacao_completo.md) na raiz.

## Camadas

```
PRESENTATION (api/routers/ + orgconc-react/)
        ↓ handlers magros
APPLICATION (api/usecases/)
        ↓ orquestra entidades + interfaces
DOMAIN (api/domain/) ◄── ZERO import de FastAPI/SQLAlchemy/anthropic
        ↑ implementa Protocols
INFRASTRUCTURE (api/infra/)
        ↓ + cross-cutting
OBSERVABILITY / SECURITY (api/observability/, api/middleware/, api/core/)
```

## Regras de dependência

- `domain/` **não importa** nada externo. Só Python stdlib.
- `usecases/` importa só `domain/`.
- `infra/` importa `domain/` (para implementar Protocols).
- `routers/` importa `usecases/` + Pydantic.
- `main.py` faz o wiring (via `api/wiring.py`).

## ADRs

Decisões registradas em [`docs/ADRs/`](./ADRs/) — apenas as não-óbvias.

## Stack confirmado

| Camada | Tecnologia |
|---|---|
| API | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.x async + asyncpg + Supabase pooler |
| Auth | JWT HS256 + bcrypt + refresh tokens rotativos |
| LLM | Anthropic SDK (Claude 4.x) |
| Fila | Arq + Redis |
| Cache / rate-limit | Redis |
| Storage | LocalStorage (FS) | S3 (Supabase Storage) |
| Métricas | Prometheus client (`/metrics`) |
| Erros | Sentry |
| Frontend | React 19 + Vite + Tailwind + shadcn/ui + TanStack Query |
| Testes | pytest, vitest, Playwright + axe-core |
| Lint | ruff (Python), eslint (TS); mypy strict em domain/usecases |

## Diretrizes para novas features

1. Modelo de domínio primeiro. `entities.py` ou `value_objects.py`.
2. Use case em `api/usecases/<feature>.py` com Input/Output dataclasses.
3. Interface (Protocol) em `domain/repositories.py` se precisar de infra nova.
4. Implementação concreta em `api/infra/<sub>/`.
5. Wiring em `api/wiring.py`.
6. Router fino: `Depends(use_case_factory)`.
7. `response_model=` Pydantic em `schemas_responses.py`.
8. Erros via `DomainError` (vira RFC 7807 automaticamente).
9. Teste unit do use case mockando o Protocol.

## Cross-cutting

- **Request-ID** propagado em `X-Request-ID` (header e log).
- **PII masking** automático nos logs (`mask_pii` em `services/logging_estruturado.py`).
- **Audit middleware** persiste todas as mutações em `audit_log`.
- **Prometheus middleware** instrumenta `http_requests_total` e duração.
- **Security headers** (CSP, HSTS, etc.) em todas as responses.
