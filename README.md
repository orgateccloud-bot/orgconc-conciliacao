# ORGATEC · OrgConc

Conciliação bancária inteligente **+ auditoria fiscal forense**. Cruza extratos OFX/PDF/XML,
detecta anomalias, enriquece CNPJs (RFB/BrasilAPI), calcula risco tributário e gera laudos
HTML/XLSX/PDF. Multi-tenant (RLS por `org_id`), em produção no Railway + Supabase.

> **Versão:** 0.5.0 — beta avançado em produção · **Mapa técnico:** [`PROJETO_MAPEAMENTO_COMPLETO.md`](PROJETO_MAPEAMENTO_COMPLETO.md) · **Roadmap:** [`docs/ROADMAP_1.0.md`](docs/ROADMAP_1.0.md)

## Stack

- **Backend**: FastAPI · routers modulares · auth JWT multi-org + token legacy · SQLAlchemy async
- **Frontend**: `orgconc-react/` (Vite + React 19 + Tailwind 4 + shadcn/ui), servido em `/app`
- **Banco**: PostgreSQL / Supabase com **RLS real por `org_id`** (FORCE RLS, fail-closed)
- **Fiscal**: pipeline forense (cascata de 6 estágios) + laudo (WeasyPrint) + CBS/IBS (orquestra calculadora oficial)
- **Deploy**: Railway (Docker multi-stage); observabilidade Prometheus `/metrics` + Sentry

## Desenvolvimento

```bash
pip install -r requirements.txt
cp .env.example .env

# Terminal 1 — API
python -m uvicorn api.main:app --host 127.0.0.1 --port 8765 --reload

# Terminal 2 — React (proxy para API)
cd orgconc-react && npm install && npm run dev
```

- API: http://127.0.0.1:8765/docs
- React (dev): http://127.0.0.1:5176

## Produção (React servido pela API)

```bash
cd orgconc-react && npm run build
python -m uvicorn api.main:app --host 0.0.0.0 --port 8765
```

App React (same-origin): http://127.0.0.1:8765/app/

## Auth

| Variável | Descrição |
|----------|-----------|
| `ORGCONC_JWT_SECRET` | Obrigatório em `ORGCONC_ENV=production` |
| `ORGCONC_ADMIN_EMAIL` / `ORGCONC_ADMIN_SENHA_HASH` | Login admin `/auth/login` (bcrypt) |
| `ORGCONC_AUTH_TOKEN` | Token legacy (scripts/CI) — aceito junto com JWT |

Em produção, endpoints protegidos exigem `Authorization: Bearer <jwt|legacy>`. O JWT carrega `org_id`,
que alimenta o contexto RLS por request. Usuários multi-org fazem login por usuário (ver `routers/auth_routes.py`).

## Endpoints principais

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/conciliar/ofx` | Upload 1–50 arquivos; `?simular=true` sem LLM |
| POST | `/conciliar/csv` | Extrato + razão CSV |
| GET | `/conciliacoes` | Histórico (requer DB) |
| GET | `/export/html\|xlsx\|pdf/{rid}` | Exportações |
| POST | `/fiscal/processar` · `/fiscal/laudo` | Pipeline forense + laudo (XLSX/MD/HTML/PDF) |
| POST | `/fiscal/apurar` | Apuração CBS/IBS (orquestra calculadora oficial) |
| GET | `/fiscal/{conformidade\|gap\|risco-tributario}/{id}` | Resultados fiscais |
| GET | `/metrics` · `/health` | Prometheus + healthcheck |

São **56 endpoints** em **16 routers**. Lista completa em `/docs` (OpenAPI).

## Testes

```bash
pip install -r requirements-dev.txt
pytest tests/ -v          # 737 testes; gate de cobertura 80% no CI

cd orgconc-react && npm test    # Vitest (unit) · npx playwright test (e2e)
```

Testes de integração com Postgres (`test_db_*`) rodam só se `DATABASE_URL` estiver acessível.
Para forçar mesmo com URL inválida (debug): `ORGCONC_RUN_DB_TESTS=1 pytest tests/ -k test_db_`.

## Estrutura

```
api/
  main.py              # App factory + mounts (React em /app)
  routers/             # 16 routers: health, auth, clientes, conciliacao, fiscal, exports...
  services/            # laudo_forense, excel, fiscal_persistence, calculadora_cbs_ibs, auth...
  matchers/            # pipeline forense: forensics, cnpj_enricher, xml_fiscal, orquestrador
  parsers/             # ofx, xml, pdf, csv, classifier, anomalies
  db/                  # ORM async (19 entidades), contexto RLS, metrics
  core/                # config, prometheus, observability, rate-limit
orgconc-react/         # UI principal (React 19 + Vite + Tailwind 4)
migrations/versions/   # 20 migrations Alembic (head: 020_org_id_fiscais)
tests/                 # 40 arquivos, 518 funções
docs/                  # roadmap, runbooks, planejamento
```

## Licença

Privado · © ORGATEC Contabilidade e Auditoria
