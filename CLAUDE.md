# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Respostas e comentários em **português do Brasil**.

## O que é

**ORGATEC · OrgConc** — API + SPA de **conciliação bancária** para escritórios contábeis brasileiros. Recebe extratos (OFX/PDF/XML/CSV/MD) e/ou razão contábil, cruza por data/valor/descrição, detecta anomalias (duplicidade, valor alto, estorno, transferência sem par), classifica contabilmente e gera relatório (HTML/XLSX/PDF) com apoio de LLM (Claude).

Backend FastAPI (`api/`) + frontend React 19/Vite (`orgconc-react/`) servido em `/app`. Persistência opcional em Postgres/Supabase; sem banco, cai para JSON local em `data/`.

## Comandos

Backend (raiz do projeto, Python 3.12, Windows):
```powershell
pip install -r requirements-dev.txt     # inclui requirements.txt + ferramentas
uvicorn api.main:app --reload --host 127.0.0.1 --port 8765

# Testes (suite real fica em tests/, NÃO os teste*.py soltos na raiz)
python -m pytest tests/ -q              # tudo
python -m pytest tests/test_api.py -q   # um arquivo
python -m pytest tests/test_api.py::nome_do_teste   # um teste
python -m pytest tests/ --cov           # cobertura (config em pyproject.toml)

ruff check api tests        # lint  (config em pyproject.toml)
mypy api/domain api/usecases   # type-check strict só nesses módulos

# Migrações (DATABASE_URL no .env; alembic/env.py sobrescreve sqlalchemy.url)
alembic upgrade head
alembic revision --autogenerate -m "descricao"
```

Worker assíncrono (fila Arq sobre Redis):
```powershell
arq api.workers.WorkerSettings
```

Frontend (`orgconc-react/`):
```powershell
npm install
npm run dev          # Vite em :5173, com proxy para o backend
npm run build        # gera orgconc-react/dist (servido pelo backend em /app)
npm run typecheck    # tsc -b
npm run lint         # eslint
npm run test         # vitest run  (test:watch / test:cov disponíveis)
```

## Notas críticas

- **Porta do backend:** **8765** em todos os pontos (`launch.json`, docstring de `api/main.py` e proxy do Vite em `vite.config.ts`). Mantenha alinhado se mudar.
- **Versão única:** o arquivo `VERSION` na raiz é a fonte da verdade (lido por `api/core/config.py`). Mantenha `orgconc-react/package.json` em sincronia (via `bump-my-version`, config em `.bumpversion.toml`).
- **`.claude/worktrees/` e `**/node_modules/`:** cópias de trabalho/deps — ignore ao buscar/editar. Edite sempre na raiz do projeto.
- **Scripts soltos na raiz** (`teste_*.py`, `teste2.py`, `conciliar_ofx.py`, `resultado.py`, etc.) são experimentos ad-hoc, **não** a suíte de testes. A suíte é `tests/`.
- **Testes e banco:** `tests/conftest.py` pula o DB automaticamente quando `DATABASE_URL` é placeholder/inacessível e troca o engine por `NullPool`. Para rodar testes que dependem do Postgres, defina `ORGCONC_RUN_DB_TESTS=1`.
- **OCR/Vision:** PDFs sem texto usam Tesseract (binário em `C:\Program Files\Tesseract-OCR`) e, sob `?vision=true`, fallback via Claude Vision. `ANTHROPIC_API_KEY` é necessária para LLM/Vision.

## Arquitetura do backend (`api/`)

Arquitetura em camadas (Clean-ish). A dependência aponta para dentro: `routers → usecases → domain`, com `infra` implementando as interfaces de `domain`.

- **`domain/`** — regras de negócio puras, sem IO nem framework. `entities.py`, `value_objects.py`, `services.py` (classificador contábil heurístico multi-banco + `DetectorAnomalias`), `repositories.py` (interfaces), `exceptions.py`. Único módulo (com `usecases`) sob `mypy --strict`.
- **`usecases/`** — orquestram domínio + repositórios (`CriarClienteUseCase`, `ListarConciliacoesUseCase`, ...).
- **`infra/`** — implementações: `repositories/` (SQL via SQLAlchemy async), `queue/` (pool Arq), `storage/` (gateway local + S3), `excel/`.
- **`wiring.py`** — **Dependency Injection**. Todas as factories `Depends()` ficam aqui; routers só declaram dependências, nunca instanciam infra. `get_db_session` retorna 503 se o banco não estiver configurado.
- **`routers/`** — endpoints. `conciliacao.py` é o coração (`/conciliar/ofx`, `/conciliar/csv`). `health`/`auth_routes` são rotas de plataforma (sem versão); negócio é montado com prefixo **`/v1`** e também duplicado **sem prefixo** para retrocompat (será removido).
- **`parsers/`** — `router.py::_parse_arquivo` detecta extensão e roteia para `ofx`/`pdf`/`xml_parser`/`markdown`. `pdf.py` tem caminho OCR (`pdf_ocr.py`); `services/vision_pdf.py` é o fallback Vision.
- **`services/`** — `conciliacao_llm.py` (chama Claude: single, multi-modelo com `sintetizar_consenso`, ou simulação local via `relatorio_local.py`), `render.py` (Markdown→HTML), `excel.py`, `db_persistence.py`, `storage.py` (datasets JSON), `auth.py` (JWT + `current_user`), `serpro_consulta.py` (consulta CNPJ/CPF SERPRO), `feature_flags.py`, `sanitize.py`.
- **`db/`** — `client.py` (engine/SessionLocal async + `Base`), `models.py` (SQLAlchemy espelhando o schema Supabase: `Org`/`Cliente`/`Conciliacao`/`Transacao`/`Job`/`FeatureFlag`/`AuditLog`/`RefreshToken`; multi-tenant por `org_id`, `DEFAULT_ORG_ID` para retrocompat), e CRUD por entidade.
- **`core/`** — `config.py` (todas as env vars `ORGCONC_*`, flags globais como `DB_DISPONIVEL`, `SYSTEM_PROMPT`, `_MODELOS_VALIDOS`, validação obrigatória em produção), `rate_limit.py` (slowapi/Redis), `exception_handlers.py` (RFC 7807 Problem Details), `templates.py`.
- **`middleware/`** + **`observability/`** — `AuditMiddleware`, `RequestIdMiddleware`, headers de segurança (CSP/HSTS) em `main.py`, métricas Prometheus em `/metrics`, Sentry.
- **`workers/`** — tasks Arq (`tasks.py`, `settings.py`). Nota: a lógica completa de conciliação async ainda vive no router; `conciliar_ofx_task` é esqueleto a ser plugado.

### Fluxo de `/v1/conciliar/ofx`
parse de cada arquivo (`_parse_arquivo`, com fallback Vision para PDF) → `_detectar_anomalias` (heurístico, domínio) → ramo conforme flags:
- `simular=true` → relatório 100% local (`_conciliacao_local`);
- `multi_modelo=true` → chama Opus/Sonnet/Haiku em paralelo + `sintetizar_consenso` (devolve `score_consenso`);
- padrão → um modelo (`?modelo=haiku|sonnet|opus`).

Sempre: `salvar_dataset` (JSON local) + `salvar_no_banco` (best-effort se DB) → resposta com `relatorio_md`, `relatorio_html` e `anomalias`.

## Frontend (`orgconc-react/`)

React 19 + Vite + TypeScript, **TanStack Query** para dados de servidor, **react-router-dom** com `basename="/app"`, **shadcn/ui** (Radix em `src/components/ui/`) + Tailwind. Páginas em `src/pages/` (Dashboard, Conciliação, Clientes, Relatórios, Configurações) carregadas via `lazy()`. Alias `@` → `src/`.

- **`src/lib/api.ts`** — cliente HTTP central (`apiFetch`). Access token JWT em `sessionStorage`; em **401** tenta `/auth/refresh` (cookie httpOnly) uma vez antes de deslogar. Todas as chamadas de negócio batem em `/v1/...`.
- **`src/lib/auth.tsx`** — `AuthProvider`/`useAuth`; `ProtectedRoute` em `App.tsx` protege as rotas.
- Design system documentado em `design-system/MASTER.md` (tema "Aurora Blue", glassmorphism, light mode).

## Variáveis de ambiente (`.env` na raiz)

`DATABASE_URL` (Supabase/Postgres; vazio/placeholder ⇒ modo JSON local), `ANTHROPIC_API_KEY`, `ORGCONC_ENV` (`production` ativa validações + HSTS), `ORGCONC_CORS_ORIGINS` (obrigatório em prod), `ORGCONC_JWT_SECRET` (≥32 chars em prod), `ORGCONC_ADMIN_EMAIL`/`ORGCONC_ADMIN_SENHA_HASH`, `ORGCONC_MAX_UPLOAD_MB`/`_TOTAL_MB`, `ORGCONC_DATA_DIR`, `ORGCONC_LOG_JSON`/`_LEVEL`, `REDIS_*` (rate limit + Arq). Veja a lista canônica em `api/core/config.py`.
