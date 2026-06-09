# Relatório Executivo — OrgConc

**Data:** 2026-06-09 · **Versão:** 0.5.0 (beta avançado em produção) · **Nota geral:** **7.8/10** (era 7.6)

Documentos de referência: [Mapeamento técnico](PROJETO_MAPEAMENTO_COMPLETO.md) · [Planejamento](docs/PLANEJAMENTO_EXECUCAO.md) · [Roadmap 1.0](docs/ROADMAP_1.0.md)

---

## 1. Onde o projeto está

OrgConc é uma plataforma de **conciliação bancária + auditoria fiscal forense**, multi-tenant, rodando
em produção (Railway + Supabase). O diferencial é o **pipeline fiscal forense** (cascata de 6 estágios,
enriquecimento de CNPJ via RFB, detecção de fraude, regime×teto) que **reproduz laudo real ao centavo**.

| Camada | Tamanho | Maturidade |
|--------|---------|------------|
| Backend (FastAPI) | 15.988 LOC · 56 endpoints · 16 routers · 19 entidades | 🟢 Madura, multi-tenant |
| Frontend (React 19 + Tailwind 4) | 9.164 LOC · 17 páginas | 🟡 UX madura, testes baixos |
| Testes | 518 backend (gate 74%) · 5/17 páginas · 4 E2E | 🟡 Backend forte, frontend fraco |
| Banco | 20 migrations · RLS real por `org_id` (fail-closed) | 🟢 Production-grade |
| DevOps | Railway Docker · Prometheus + Sentry · CI 4 jobs | 🟢 Resolvido (falta staging) |

---

## 2. Evolução desde o último mapeamento (2026-06-02)

Em ~40 PRs (#61–#101), a grande conquista foi **multi-tenancy de produção**:

- ✅ **RLS real por `org_id`** — FORCE RLS, `app_orgconc` sem bypass, owner separado para migrations,
  superadmin cross-org read-only, re-auditado live (fail-closed provado).
- ✅ **Login ORGATEC** + usuários multi-org + reset/troca de senha com revogação de refresh.
- ✅ **Admin** — página de gestão de usuários e organizações.
- ✅ **Dashboard redesenhado** — empty-first honesto, bento, a11y, command palette ⌘K, cache por tenant.
- ✅ **Stack atualizada** — Tailwind 4 (CSS-first), bcrypt 5 (passlib removido), GH Actions bump.

Crescimento: backend +14% LOC, +7 endpoints, +8 migrations, +72 testes.

---

## 3. Achados do remapeamento (drift & dívidas)

| # | Achado | Severidade | Situação |
|---|--------|------------|----------|
| A2/A3 | README citava `static/`/`/ui/` inexistente; comentário em `main.py` citava GitHub Pages removido | 🟡 Baixa | ✅ **Corrigidos neste ciclo** |
| A1 | **SERPRO ainda em 5 arquivos** vs decisão de removê-lo (alvo: API portal Tributos) | 🟠 Média | Planejado (Sprint 2) |
| A4 | **12/17 páginas frontend sem teste** (proporção piorou) | 🟠 Média | Planejado (Sprint 1) |
| A7 | **Logout não revoga refresh token** (vale até o TTL) | 🟠 Média | Planejado (Sprint 1) |
| A5 | 3 policies RLS legadas inertes a limpar | 🟡 Baixa | Planejado (Sprint 2) |
| A6 | Fat file `laudo_forense.py` cresceu (2.089 LOC) | 🟡 Baixa | Planejado (Sprint 2) |

---

## 4. Pontuação por dimensão

```
Backend:           8.0/10  ████████░
Frontend:          7.0/10  ███████░░
Testing:           7.0/10  ███████░░
DevOps:            8.0/10  ████████░
Documentation:     7.5/10  ███████░░
Security:          8.5/10  ████████▌   ↑ RLS real + bcrypt 5 + revogação
Observability:     8.0/10  ████████░
Maintainability:   7.0/10  ███████░░
──────────────────────────────────────
GERAL:             7.8/10  ████████░   (era 7.6)
```

---

## 5. Plano para 1.0 (resumo)

| Sprint | Foco | Itens-chave | Nota projetada |
|--------|------|-------------|----------------|
| **1 (1–2 sem)** | Endurecimento P0 | cobertura frontend + gate · revogação no logout · rate-limit testado · E2E profundo | ~8.1 |
| **2 (2–4 sem)** | Fiscal P1 | remover SERPRO → API oficial · persistir apuração CBS/IBS · catálogo anomalias AN-01..18 · refator laudo · limpar RLS | ~8.5 |
| **3 (1–2 mês)** | Governança P2 | CHANGELOG + `/v1` · staging 🔑 · jobs assíncronos 🔑 · TS strict · SLA/SLO 🔑 | 1.0 formal |

Detalhe com critérios de aceite em [`docs/PLANEJAMENTO_EXECUCAO.md`](docs/PLANEJAMENTO_EXECUCAO.md).

**Dependem de você (🔑):** spec da API oficial do portal Tributos, staging (Railway env + Supabase branch),
worker/fila para jobs assíncronos, metas SLA/SLO + rotação de segredos.

---

## 6. Recomendação

**Status:** production-ready multi-tenant. A fundação (RLS, auth, conciliação, laudo forense, CI/CD)
está em nível de produção; o caminho para 1.0 é **abrangência + endurecimento, não reconstrução**.

**Próximo passo imediato (autônomo):** Sprint 1 — fechar a maior lacuna de qualidade (cobertura
frontend com gate) e o item de segurança pendente (revogação de refresh no logout). Maior dependência
externa: **ambiente de staging**, citado como a lacuna nº 1.

---

**Gerado:** 2026-06-09 · Métricas medidas no estado atual do worktree (`git ls-files`/`wc`/`grep`).
