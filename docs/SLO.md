# SLO / SLA — OrgConc (P2 #12)

> **Metas VIGENTES desde 2026-06-10** (aprovadas pelo owner) com base na
> instrumentação existente (Prometheus `/metrics`, Sentry, log JSON com
> `request_id`, synthetic monitor de 30 min — incluindo a sonda de banco do
> #123 —, healthcheck Railway). Renegociar números quando houver SLA
> contratual com cliente.

## SLOs (janela de 30 dias)

| # | Indicador (SLI) | Meta (SLO) | Fonte de medição |
|---|---|---|---|
| 1 | Disponibilidade do `GET /health` | **≥ 99,5%** (~3h39m de orçamento de erro/mês) | synthetic-monitor (30 min) + healthcheck Railway |
| 2 | Taxa de erro 5xx (todas as rotas) | **< 1%** das requisições | Prometheus `http_requests_total` por status |
| 3 | Latência p95 — rotas de leitura (dashboard, listagens) | **< 800 ms** | Prometheus `request_duration` |
| 4 | Latência p95 — processamento fiscal (`/fiscal/processar`, `/fiscal/laudo`) | **< 60 s** (síncrono; o caminho assíncrono via fila #122 responde 202 imediato e não conta aqui) | Prometheus `request_duration` |
| 5 | Durabilidade de dados | RPO ≤ 24h (backup diário Supabase) · RTO ≤ 4h | BACKUP.md |

## Política de orçamento de erro

- Orçamento do SLO 1 estourado no mês → **congela** deploys de feature até a
  causa estar mitigada (só correções entram); post-mortem leve no CHANGELOG.
- 2 incidentes com a mesma causa-raiz → item de hardening obrigatório no roadmap.

## Resposta a incidente

1. Sinal: synthetic monitor falhou (uptime OU sonda de banco do #123) /
   Sentry alert / usuário.
2. Diagnóstico: `RUNBOOK.md` §5 (runtime sem banco — sonda `/auth/refresh`,
   rotação parcial de senha) e o caso clássico **Supabase pausado** (TCP ok,
   handshake Postgres timeout → retomar no dashboard e reiniciar).
3. Rollback: redeploy do deployment anterior no Railway (RUNBOOK.md §rollback).
4. Registro: entrada no CHANGELOG (`### Corrigido`) com link do incidente.

## Revisão

Revisar metas trimestralmente ou quando: (a) jobs assíncronos (P1 #9) entrarem,
(b) multi-réplica for ativada (rate-limit/custo-LLM ainda in-memory), (c) SLA
contratual for assinado com cliente.
