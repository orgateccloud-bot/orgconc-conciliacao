# OrgConc — Makefile de desenvolvimento
# Roda no Windows via Git Bash, WSL, Linux ou macOS.

.DEFAULT_GOAL := help

PY ?= python
NPM ?= npm
FRONT_DIR := orgconc-react

.PHONY: help install install-prod dev frontend test test-frontend test-all \
        lint format typecheck security build clean

help: ## Lista comandos disponiveis
	@awk 'BEGIN{FS=":.*##"; printf "Comandos:\n"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Instala dependencias dev (backend + frontend)
	$(PY) -m pip install -r requirements-dev.txt
	cd $(FRONT_DIR) && $(NPM) ci

install-prod: ## Instala somente prod (sem pytest/ruff/etc)
	$(PY) -m pip install -r requirements-prod.txt

dev: ## Sobe API local em 8765 (autoreload)
	$(PY) -m uvicorn api.main:app --reload --port 8765

frontend: ## Sobe Vite dev server em 5173
	cd $(FRONT_DIR) && $(NPM) run dev

test: ## Roda pytest backend com cobertura
	$(PY) -m pytest --cov=api --cov-report=term-missing

test-frontend: ## Roda Vitest frontend
	cd $(FRONT_DIR) && $(NPM) run test:run

test-all: test test-frontend ## Backend + frontend

lint: ## ruff + black --check
	$(PY) -m ruff check api/ tests/
	$(PY) -m black --check api/ tests/

format: ## Aplica black + ruff --fix
	$(PY) -m ruff check --fix api/ tests/
	$(PY) -m black api/ tests/

typecheck: ## TypeScript noEmit no frontend
	cd $(FRONT_DIR) && npx tsc --noEmit

security: ## pip-audit + bandit + semgrep
	$(PY) -m pip_audit -r requirements-prod.txt
	$(PY) -m bandit -r api/ -ll
	$(PY) -m semgrep --config=auto api/ --error --quiet || true

build: ## Build do frontend para producao
	cd $(FRONT_DIR) && $(NPM) run build

clean: ## Remove caches e build artefacts
	rm -rf .pytest_cache .coverage htmlcov __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(FRONT_DIR)/dist $(FRONT_DIR)/node_modules/.vite
