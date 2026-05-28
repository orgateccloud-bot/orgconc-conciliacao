# ORGATEC · Conciliação Bancária (OrgConc)

API e UI para conciliação bancária inteligente. Cruza extratos OFX/PDF/XML, detecta anomalias, gera relatórios HTML/XLSX/PDF.

## Stack

- **Backend**: FastAPI 0.5 · routers modulares · JWT + token legacy
- **Frontend principal**: `orgconc-react/` (Vite + React 19 + Tailwind + shadcn)
- **UI legada** (transição): `static/` em `/ui/`
- **Banco**: PostgreSQL/Supabase opcional

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
- UI legada: http://127.0.0.1:8765/ui/

## Produção (React servido pela API)

```bash
cd orgconc-react && npm run build
python -m uvicorn api.main:app --host 0.0.0.0 --port 8765
```

App React: http://127.0.0.1:8765/app/

## Auth

| Variável | Descrição |
|----------|-----------|
| `ORGCONC_JWT_SECRET` | Obrigatório em `ORGCONC_ENV=production` |
| `ORGCONC_ADMIN_EMAIL` / `ORGCONC_ADMIN_SENHA_HASH` | Login `/auth/login` |
| `ORGCONC_AUTH_TOKEN` | Token legacy (scripts/CI) — aceito junto com JWT |

Em produção, endpoints protegidos exigem `Authorization: Bearer <jwt|legacy>`.

## Endpoints principais

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/conciliar/ofx` | Upload 1–50 arquivos; `?simular=true` sem LLM |
| POST | `/conciliar/csv` | Extrato + razão CSV |
| GET | `/conciliacoes` | Histórico (requer DB) |
| GET | `/export/html\|xlsx\|pdf/{rid}` | Exportações |

## Testes

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Testes de integração com Postgres (`test_db_*`) rodam só se `DATABASE_URL` estiver acessível.
Para forçar mesmo com URL inválida (debug): `ORGCONC_RUN_DB_TESTS=1 pytest tests/ -k test_db_`.

## Estrutura

```
api/
  main.py              # App factory + mounts
  routers/             # health, auth, clientes, conciliacao, exports
  services/            # persistencia, conciliacao_llm, excel
  parsers/             # ofx, xml, pdf, classifier, anomalies, stats
orgconc-react/         # UI principal
static/                # UI legada (deprecated)
tests/
```

## Licença

Privado · © ORGATEC Contabilidade e Auditoria
