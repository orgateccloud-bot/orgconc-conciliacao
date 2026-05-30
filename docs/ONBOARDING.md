# Onboarding — OrgConc (30 minutos)

> Setup mínimo para um dev novo rodar o stack localmente. Para deploy, veja [`../DEPLOY.md`](../DEPLOY.md).

## Pré-requisitos

- Python **3.12+**
- Node **22+**
- Git
- (Recomendado) Docker Desktop

## 1. Clonar + envs

```bash
git clone <repo>
cd OrgConc
cp .env.example .env
```

Mínimo viável para `.env` em dev:

```env
ANTHROPIC_API_KEY=sk-ant-...           # sua chave
ORGCONC_JWT_SECRET=qualquer-coisa-com-pelo-menos-32-chars-aqui
ORGCONC_ADMIN_EMAIL=dev@orgatec.cloud
# Gere com curl POST /auth/hash uma vez que a API estiver no ar; cola aqui:
ORGCONC_ADMIN_SENHA_HASH=
DATABASE_URL=                          # opcional em dev — sem isso, DB skip
REDIS_URL=                             # opcional — fallback memory://
```

## 2. Backend

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows
# source .venv/bin/activate            # Linux/Mac
pip install -r requirements-dev.txt
python -m uvicorn api.main:app --host 127.0.0.1 --port 8765 --reload
```

Validação:
- Swagger: <http://127.0.0.1:8765/docs>
- `curl http://127.0.0.1:8765/health/live` → `{"status":"ok"}`

## 3. Frontend

```bash
cd orgconc-react
npm install
npm run dev                            # http://127.0.0.1:5173
```

## 4. Gerar senha admin

Com a API no ar e `ORGCONC_ENV=development`:

```bash
curl -X POST http://127.0.0.1:8765/auth/hash \
  -H "Content-Type: application/json" \
  -d '{"senha":"Sua-Senha-Forte-Aqui-12chars"}'
```

Copia o `hash` retornado para `ORGCONC_ADMIN_SENHA_HASH` no `.env` e reinicia.

## 5. Testes

```bash
# Backend
pytest -v --cov=api

# Frontend (unit)
cd orgconc-react && npm test

# Frontend (E2E — requer API + frontend rodando)
cd orgconc-react && npx playwright test
```

## 6. Stack completo via Docker

```bash
docker compose up -d --build
```

URLs:
- API: <http://localhost:8000>
- React: <http://localhost:8000/app/>
- Health: <http://localhost:8000/health>

## 7. Próximos passos

- Leia [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- Leia [`SECURITY.md`](./SECURITY.md)
- Para incidentes: [`RUNBOOK.md`](./RUNBOOK.md)
- Roadmap completo: [`../projeto_implementacao_completo.md`](../projeto_implementacao_completo.md)

## Problemas comuns

| Sintoma | Solução |
|---|---|
| `RuntimeError: ORGCONC_JWT_SECRET obrigatorio` | Defina no `.env` (>= 32 chars) |
| `Connection refused` ao login | API não está rodando |
| `Token Bearer obrigatorio em producao` | Está com `ORGCONC_ENV=production` em dev. Mude para `development`. |
| weasyprint quebra ao exportar PDF | Linux: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2`. Windows: use Docker. |
