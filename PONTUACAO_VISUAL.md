# OrgConc — Dashboard de Pontuação & Prioridades

**Atualizado:** 2026-06-12 · régua recalibrada (8 = sólido c/ defeitos menores · 7 = bom c/ dívidas reais · 9+ = exemplar, raro)
**Método:** repontuação por avaliadores independentes com rubrica única, evidência file:line, falsos-positivos descartados (2026-06-11/12)
**Snapshot anterior:** [docs/historico/PONTUACAO_VISUAL_2026-05-28.md](docs/historico/PONTUACAO_VISUAL_2026-05-28.md) (baseline 6.4) · complementa [docs/ESTADO_PROJETO_2026-06-11.md](docs/ESTADO_PROJETO_2026-06-11.md)

---

## 📊 SCORECARD GERAL

```
BACKEND ARCHITECTURE          7.2/10  ███████░░░  (Sólido; fat files no services/)
FRONTEND ARCHITECTURE         7.5/10  ████████░░  (TS strict REAL desde 06-11; 17/17 páginas testadas)
TESTING & COVERAGE            8.0/10  ████████░░  (770 backend gate 80 · 352 front ~88% gate 84/86)
DEVOPS & DEPLOYMENT           6.5/10  ███████░░░  (→ ~7.2 após merge dos PRs #132–#135)
DOCUMENTATION                 7.5/10  ████████░░  (sincronizada com o código em 06-11/12)
SECURITY                      8.5/10  █████████░  (RLS ativo + 2 rodadas de hardening + reuse-detection)
OBSERVABILITY                 8.0/10  ████████░░  (Sentry+PII · Prometheus c/ token · sonda 30min)
MAINTAINABILITY               7.0/10  ███████░░░  (laudo_forense 2.1k LOC; domínio semi-órfão)
════════════════════════════════════════════════════════════
🎯 OVERALL SCORE              7.5/10  ████████░░  (Production-ready multi-tenant)
```

> ⚠️ **Régua recalibrada** — não compare valor absoluto com snapshots antigos:
> 6.4 (05-28) → 7.6 (06-02) → 7.8 (06-09, régua antiga) → **7.5 (06-12, régua dura)**.
> Na régua antiga o estado atual estaria ≈ 8.0+. A tendência real é de melhora contínua.

---

## 🔍 BACKEND POR MÓDULO (repontuado 2026-06-11)

```
core/                  [████████░░] 7.5  Hardening forte; middlewares de segurança agora testados
db/                    [████████░░] 7.5  RLS fail-closed ativo; CRUDs sem filtro org_id próprio (P1)
matchers/              [████████░░] 7.5  Cascata+forense maduras; consulta global de tenant (P1)
parsers/               [████████░░] 7.5  anomalies/xml ótimos; PDF 0% testes, classifier raso
routers/               [███████░░░] 7.0  Autorização centralizada; fiscal.py segue fat (802 LOC)
services/              [███████░░░] 6.5  laudo_forense 2.1k LOC funde coleta+cálculo+render
schemas/ + main.py     [████████░░] 7.5  CNPJ c/ DV, anti-timing; cobertura de schemas ~7%
domain/infra/usecases  [███████░░░] 6.5  Menos órfã que dito; duplicação db/ × infra/ p/ clientes
```

## 🚀 DEVOPS POR EIXO (repontuado 2026-06-11 · projeção pós-merge #132–#135)

```
                        hoje   pós-merge
CI/CD Tests             6.5 →  7.5   #134: semgrep/Trivy BLOQUEANTES + trivy-action por SHA
CI/CD Deploy            6.0 →  6.0   Railway nativo + preDeploy; falta smoke on-deploy/rollback doc → #135 cobre rollback
Observability           8.0 →  8.0   Eixo mais forte; 22 testes diretos dos middlewares (06-11)
Deployment Docs         7.0 →  7.5   DEPLOY/STAGING/RUNBOOK reais; fluxo fantasma removido (06-12)
Railway Config          7.0 →  8.0   #133: container non-root (uid 10001, código read-only)
Staging Env             5.5 →  5.5   Existe e valida migrations; sem paridade RLS/Supabase branch
Disaster Recovery       5.5 →  7.0   #132: restore REAPLICA RLS; render.yaml/Procfile removidos
                                     #135: sonda do incidente 06-10 + rotação app_orgconc no RUNBOOK
─────────────────────────────────────
média                   6.5 →  7.2   (era 3.0 em 05-28)
```

## 🧪 TESTES (2026-06-12)

```
Backend (pytest)   ████████░░  770 testes · gate 80% bloqueante · +22 hardening +RLS real no CI
Frontend (vitest)  █████████░  352 testes · ~88% · gate 84/76/83/86 · tsc strict limpo
E2E (Playwright)   ████░░░░░░  4 specs happy-path (aprofundar: upload→resultado, forense)
RLS (CI)           ████████░░  Postgres real + role NOBYPASSRLS, fail-closed provado
```

---

## 🚨 PRIORIDADES ABERTAS

| # | Item | Sev. | Origem |
|---|------|------|--------|
| 1 | Hash chain de auditoria: metadados fora do hash + sem lock de concorrência | 🟠 P1 | ESTADO_PROJETO §5.1 |
| 2 | `org_id` explícito nas agregações de `db/metrics.py` (defesa em profundidade; hoje só RLS) | 🟠 P1 | ESTADO_PROJETO §5.2 |
| 3 | Filtro de tenant nos matchers (`documento.py`, `contrapartes.py`) | 🟠 P1 | ESTADO_PROJETO §5.3 |
| 4 | Rate-limiter e custo-LLM in-memory (degradam multi-instância) | 🟡 P1 | memória multi-instância |
| 5 | `pdf.py` sem testes + sem limites estruturais; `fitid` morto | 🟡 P1 | repontuação parsers |
| 6 | Duplicação `db/clientes.py` × `infra/repositories/clientes.py` | 🟡 P2 | repontuação domain |
| 7 | Staging: paridade RLS (Supabase branch) + deploy automático | 🟡 P2 | repontuação DevOps |
| 8 | Exports do frontend via `apiFetchBlob` (links `<a href>` dão 401 limpo) | 🟢 P2 | ESTADO_PROJETO §5.6 |

## ✅ FECHADO DESDE O SNAPSHOT DE 05-28

GitHub Pages → Railway same-origin · deploy automatizado c/ preDeploy Alembic · 17/17 páginas
testadas (era 0/14) · staging criado · DEPLOY/RUNBOOK/BACKUP escritos · `_legacy/` removido ·
Prometheus + `/metrics` protegido · TS strict + pre-commit · RLS real em prod · 2 rodadas de
hardening (zip-bomb, logout, tenancy, reuse-detection, chunked, proxy-headers) · SAST real,
container non-root, DR com RLS (PRs #132–#135, aguardando merge).

---

## 📈 EVOLUÇÃO

```
2026-05-28   6.4/10  ██████░░░░  baseline (14 páginas sem teste, sem deploy, sem DR)
2026-06-02   7.6/10  ████████░░  deploy resolvido, cobertura subindo
2026-06-09   7.8/10  ████████░░  RLS real em prod, gates 80/86, staging
2026-06-12   7.5/10  ████████░░  régua recalibrada (≈8.0 na régua anterior) + hardening completo
```

**Próxima revisão:** após merge dos PRs #131–#135 e fechamento do P1 #1–#3.
