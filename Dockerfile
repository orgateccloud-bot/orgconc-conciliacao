# Orgconc — Backend FastAPI
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements (apenas producao — sem pytest/bandit/semgrep)
COPY requirements-prod.txt ./requirements-prod.txt

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copiar codigo da API
COPY api/ ./api/
COPY .env.example ./.env.example

# Variavel de ambiente padrao
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

# Comando de inicializacao
CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS}
