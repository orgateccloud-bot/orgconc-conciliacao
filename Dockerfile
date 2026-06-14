# Orgconc — imagem de produção: builda o frontend React e serve tudo via FastAPI.

# ── Estágio 1: build do SPA React (Vite) ─────────────────────────────
FROM node:22-slim AS frontend
WORKDIR /build
# Cacheia deps: copia manifestos antes do código-fonte
COPY orgconc-react/package.json orgconc-react/package-lock.json ./
RUN npm ci
COPY orgconc-react/ ./
RUN npm run build          # gera /build/dist (base "/app/")

# ── Estágio 2: runtime FastAPI ───────────────────────────────────────
# 3.12 para alinhar com o CI (evita divergência CI-pass vs prod-runtime).
FROM python:3.12-slim

WORKDIR /app

# Dependencias do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    # WeasyPrint (geração de PDF dos relatórios) — sem isto o PDF quebra em runtime
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python (apenas producao — sem pytest/bandit/semgrep)
COPY requirements-prod.txt ./requirements-prod.txt
RUN pip install --no-cache-dir -r requirements-prod.txt

# Codigo da API
COPY api/ ./api/
COPY .env.example ./.env.example

# Migrations Alembic — necessarias para o `alembic upgrade head` do startCommand
# (railway.json / Procfile). Sem isto o alembic falha com
# "No 'script_location' key found in configuration" e o container nao sobe.
COPY alembic.ini ./alembic.ini
COPY migrations/ ./migrations/

# Frontend compilado — FastAPI serve em /app quando orgconc-react/dist existe
COPY --from=frontend /build/dist ./orgconc-react/dist

# Variaveis de ambiente padrao
ENV PORT=8000
ENV HOST=0.0.0.0
ENV WORKERS=2
ENV ORGCONC_LOG_LEVEL=INFO
ENV ORGCONC_MAX_UPLOAD_MB=50
ENV ORGCONC_MAX_UPLOAD_TOTAL_MB=500

# Expor porta
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Comando de inicializacao.
# exec → uvicorn vira PID 1 e recebe SIGTERM (graceful shutdown no deploy).
# --proxy-headers → rate-limit e logs enxergam o IP real atrás do LB Railway
# (a rede privada garante que só o edge do Railway alcança o container).
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS} --proxy-headers --forwarded-allow-ips '*'
