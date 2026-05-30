# Orgconc — Backend FastAPI + React SPA servida em /app/
# Build em duas etapas: 1) compila o React, 2) prepara o Python e copia os assets.

# ── Stage 1: build do frontend ─────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /build/orgconc-react
COPY orgconc-react/package.json orgconc-react/package-lock.json ./
RUN npm ci
COPY orgconc-react/ ./
# A versao e injetada no bundle via vite.config.ts (le package.json)
RUN npm run build

# ── Stage 2: runtime Python ────────────────────────────────────────────────
FROM python:3.12-slim AS runtime
WORKDIR /app

# Dependencias do sistema (incluindo weasyprint, que precisa de libs nativas)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libcairo2 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Requirements primeiro para aproveitar cache do Docker
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Codigo + arquivos versionados
COPY api/ ./api/
COPY VERSION ./VERSION
COPY .env.example ./.env.example

# Assets estaticos: UI legada + bundle React do stage 1
COPY static/ ./static/
COPY --from=frontend-builder /build/orgconc-react/dist ./orgconc-react/dist

# Defaults; override via env do PaaS
ENV PORT=8000 \
    HOST=0.0.0.0 \
    WORKERS=2 \
    ORGCONC_LOG_LEVEL=INFO \
    ORGCONC_LOG_JSON=true \
    ORGCONC_MAX_UPLOAD_MB=10 \
    ORGCONC_MAX_UPLOAD_TOTAL_MB=50

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -fsS http://localhost:${PORT}/health/live || exit 1

# Em prod o numero de workers ja vem da env do PaaS; uvicorn nao aceita ${VAR}
# diretamente no exec-form, entao usamos shell-form.
CMD uvicorn api.main:app --host ${HOST} --port ${PORT} --workers ${WORKERS}
