# MONITORING — OrgConc

Setup e operação de observabilidade. Sentry é a fonte primária; logs estruturados JSON são o fallback.

## Configuração inicial

### 1. Sentry (obrigatório em prod)

1. Crie projeto FastAPI em https://sentry.io.
2. Copie o DSN.
3. Defina no provedor (Railway):
   ```
   SENTRY_DSN=https://<key>@<org>.ingest.sentry.io/<project>
   SENTRY_ENVIRONMENT=production
   SENTRY_TRACES_SAMPLE_RATE=0.1
   ORGCONC_RELEASE=v0.5.0
   ```
4. No próximo deploy, `init_sentry()` ativa. Veja log JSON `sentry_inicializado` no startup.

Verificação:
```bash
# Force um erro em prod e veja aparecer no Sentry em <30s
curl https://api.orgconc.com/nao-existe-de-proposito
# 404 — não dispara Sentry (somente >=ERROR)
# Para teste real, force uma rota que crashe (em ambiente staging)
```

### 2. Alert rules (Sentry UI)

Configure em Alerts → Create Rule:

| Quando | Filtro | Ação |
|---|---|---|
| `event.level >= error` | `environment:production` | Email + Slack |
| `event.level >= error` | `event.tags.path:/conciliar/*` | High priority |
| Issue ocorre >10x em 5min | qualquer | Page on-call |
| Issue ocorre 1x em release nova | `release:v*` | Notify deploy channel |

### 3. Métricas Prometheus (`/metrics`)

A API expõe métricas no formato Prometheus em `GET /metrics` (text/plain). O
endpoint depende de `prometheus-client` (já em `requirements-prod.txt`); se a
lib estiver ausente, o endpoint responde `503` e a aplicação segue normal.

Séries expostas (prefixo `orgconc_`):

| Métrica | Tipo | Labels | Uso |
|---|---|---|---|
| `orgconc_http_requests_total` | Counter | `method`, `path`, `status` | Throughput e taxa de erro por rota |
| `orgconc_http_request_duration_seconds` | Histogram | `method`, `path` | Latência p50/p95/p99 |
| `orgconc_http_requests_in_progress` | Gauge | (sem labels) | Concorrência em tempo real (global) |

O label `path` usa o *template* da rota (ex.: `/clientes/{cliente_id}`), não o
valor concreto, para evitar explosão de cardinalidade por IDs. O próprio
`/metrics` não é contabilizado.

Scrape config (Prometheus):
```yaml
scrape_configs:
  - job_name: orgconc
    metrics_path: /metrics
    static_configs:
      - targets: ["api.orgconc.com:443"]
    scheme: https
```

Queries úteis (PromQL):
```promql
# Taxa de erro 5xx por rota (5min)
sum(rate(orgconc_http_requests_total{status=~"5.."}[5m])) by (path)
# Latência p95 global
histogram_quantile(0.95, sum(rate(orgconc_http_request_duration_seconds_bucket[5m])) by (le))
```

### 4. Monitoramento de custo LLM (Trilha 3)

Threshold diário via env:
```
ORGCONC_LLM_COST_ALERT_USD=50  # warning quando ultrapassa
```

Logs estruturados para alimentar dashboards externos:
```json
{"msg": "llm_uso", "llm_model": "claude-sonnet-4-6",
 "llm_input_tokens": 12450, "llm_output_tokens": 3210,
 "llm_cost_total_usd": 0.085, "llm_cost_dia_usd": 12.34,
 "request_id": "abc123..."}
```

Para Grafana/Loki/Datadog, ingeste stdout do container e crie painel:
- Soma diária de `llm_cost_total_usd` group by `llm_model`
- Top 10 `request_id` por custo
- Trend semanal

## SLOs (Service Level Objectives)

| Indicador | Target | Como medir |
|---|---|---|
| Disponibilidade API | 99.5% | `/health` ping externo (UptimeRobot/StatusCake) |
| Latência p95 `/conciliar/ofx?simular=true` | <2s | Sentry Performance |
| Latência p95 `/conciliar/ofx?modelo=sonnet` | <15s | Sentry Performance (Anthropic é o gargalo) |
| Taxa de erro 5xx | <0.5% | Sentry Issues |
| Custo LLM/cliente/dia | <$5 | Log `llm_cost_dia_usd` agregado |

## Healthchecks externos

Configure UptimeRobot (free, 5min interval) ou similar:
- Monitor 1: `GET https://api.orgconc.com/health` → espera HTTP 200 + body contém `"status":"ok"`
- Monitor 2: `GET https://<frontend>/app/login` → espera HTTP 200

Notificação via email + webhook Slack/Discord.

## Logs estruturados — campos padrão

Todo log JSON tem:
- `ts` — ISO timestamp UTC
- `lvl` — INFO / WARNING / ERROR
- `logger` — orgconc.* hierárquico
- `msg` — mensagem com PII mascarado
- `request_id` — correlation ID propagado via `X-Request-ID`

Loggers úteis:
- `orgconc.http` — middleware com `method`, `path`, `status`, `duracao_ms`
- `orgconc.llm.metrics` — custo LLM (Trilha 3)
- `orgconc.observability` — startup do Sentry
- `orgconc.errors` — handler global 500 (Trilha 4)
- `orgconc.conciliacao` — endpoint de conciliação

## Métricas críticas para acompanhar

Diárias:
- Total de conciliações por modo (simular / LLM / multi_modelo)
- Custo LLM total e por modelo
- Taxa de erro 5xx
- Latência p50/p95/p99 dos endpoints principais

Semanais:
- Top 10 clientes por uso
- Crescimento MoM de conciliações
- Custo Anthropic vs. faturamento (margin guard)

## Quando escalar

Acione on-call (RUNBOOK §1) se:
- API down >5min (healthcheck falhando)
- Taxa 5xx >5% por 10min
- Custo LLM >2x do threshold em 1h
- Sentry: nova issue critical com >50 ocorrências em 5min
