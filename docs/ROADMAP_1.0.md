# Roadmap OrgConc → 1.0

> **Estado atual:** v0.5.0 — **beta avançado em produção** (Railway + Supabase, RLS real por `org_id` enforçada).
> A fundação (multi-tenancy, auth, conciliação, laudo forense, CI/CD) está em nível de produção.
> O caminho para 1.0 é **abrangência + endurecimento**, não reconstrução.
> Base: avaliação multi-agente de 2026-06-09 (7 dimensões) + correções verificadas no código.

## Legenda
- 🤖 **Autônomo** — implemento direto (código/testes/docs).
- 🔑 **Requer você** — infra, credenciais ou decisão de negócio (preparo o que der no código).
- ⚠️ Todo merge na `main` = **deploy de produção** (Railway). PRs ficam verdes aguardando sua autorização explícita.

---

## P0 — Endurecimento & confiança (alto valor, baixo risco)
| # | Item | Tipo | Entrega |
|---|------|------|---------|
| 1 | Cobertura de testes do frontend + gate no CI | 🤖 | `vitest --coverage` com threshold; testes para CommandPalette, AuditEventModal, AIInsightsPanel e páginas sem teste |
| 2 | Revogação de refresh token no logout | 🤖 | revogação real no DB; logout invalida o token na hora (hoje vale até o TTL) |
| 3 | Testes de rate-limit + headers `X-RateLimit-*` | 🤖 | cobre o throttle no CI; respostas 429 com `Retry-After`/limite |
| 4 | Limpar 3 policies RLS legadas inertes | 🤖 preparo · 🔑 aplicar | migration de `DROP POLICY` revisável; aplicação em prod coordenada |
| 5 | E2E mais profundo | 🤖 | specs: upload OFX→resultado, fluxo de auditoria, erros de negócio |

## P1 — Fiscal & abrangência (valor de negócio)
| # | Item | Tipo | Entrega |
|---|------|------|---------|
| 6 | **Remover SERPRO** + apontar a calculadora CBS/IBS para a **API oficial (portal Tributos sobre Bens e Serviços)** | 🤖 remoção/generalização · 🔑 spec do endpoint live | tira a auth OAuth2/Consumer-Key SERPRO e o naming; mantém o transporte genérico (`CALCULADORA_BASE_URL`, instância aberta/offline `consumo.tributos.gov.br`); atualiza config/testes/docs |
| 7 | Persistir apuração CBS/IBS | 🤖 | já há `apuracao_cbs_ibs` (migration 013) — garantir que `POST /fiscal/apurar` grava documento_id + versao_base + resultado + `payload_hash` |
| 8 | Catálogo de anomalias AN-01..18 no laudo | 🤖 | gerar alertas estruturados (hoje só 3 flags: MEI_SEM_CTE, REDE_FROTA_TYPE, PARTE_RELACIONADA) |
| 9 | Jobs assíncronos p/ tarefas fiscais longas | 🔑 | worker/fila no Railway (calculadora/laudo deixam de ser bloqueantes) |

## P2 — Governança & escala (rumo ao 1.0 formal)
| # | Item | Tipo | Entrega |
|---|------|------|---------|
| 10 | CHANGELOG + versionamento de API (`/v1`) + critério de 1.0 | 🤖 | governança de release |
| 11 | Staging dedicado | 🔑 | Railway env + Supabase branch (a maior lacuna citada por todos) |
| 12 | SLA/SLO + observabilidade pós-deploy | 🔑 | metas + Sentry/logs centralizados confirmados em prod |
| 13 | Rotação de segredos / key management | 🔑 | rotação do JWT secret + chaves |

---

## Ordem de execução (modo automático)
`P0 #1 → #2 → #3 → #5 → P1 #6 → #7 → P0 #4 (preparo) → P1 #8 → P2 #10`

Itens 🔑 (#9, #11, #12, #13 e a parte live do #6) ficam para quando você liberar infra/credenciais/spec.

## Critério de 1.0 (proposto)
- [ ] Cobertura: backend ≥ 80%, frontend ≥ 70% (com gate no CI).
- [ ] E2E cobrindo os fluxos críticos (conciliação, laudo, auth).
- [ ] CBS/IBS sem SERPRO, apontando a calculadora oficial + apuração persistida.
- [ ] Hardening P0 completo (refresh revogável, rate-limit testado, RLS sem drift).
- [ ] Staging + rollback + SLA/SLO documentados.
- [ ] CHANGELOG + versionamento de API.

> Histórico desta maratona (2026-06-09): #89–94 (dashboard), #95 (login), #96–98 (deps), #99 (bcrypt 5/sem passlib), #100 (Tailwind 4).
