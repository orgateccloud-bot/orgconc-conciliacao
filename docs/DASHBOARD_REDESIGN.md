# Planejamento — Remodelamento do Dashboard (OrgConc)

> Objetivo: **simplificar** o dashboard, corrigir incoerências reais e reusar a marca
> (logo `ORGATEC` + nome "Conciliação Bancária"). Baseado em análise de código de 5 lentes
> (data-states, UX, acessibilidade, código/perf, lógica de Trust Score no backend).

---

## 1. Diagnóstico (o que a análise achou)

### 🔴 Crítico — o dashboard "mente saúde" numa conta vazia
- **Backend** `api/db/metrics.py`: com `total_conciliacoes == 0`, `taxa_sucesso` cai em `100.0`
  (linha ~219) e `dias_sem_falha` vira `30` (linha ~229) → `score = round(0.5·100 + 0.3·100 + 0.2·0) = 80`
  → rótulo **"Saudável — pequenos ajustes recomendados"**. Tudo isso **sem nenhum dado**.
- **Frontend** `SecurityRing.tsx`: como o backend devolve `data` preenchido (não `null`),
  as barras mostram **"Taxa de sucesso 100%"** e **"Controle de risco 100%"**. O guard de vazio
  só pega `data === null`, nunca o caso "data existe mas zerado".
- **Efeito:** logo abaixo do herói "Nenhuma análise no período / Faça primeira análise" aparece
  um gauge **80 / Saudável** — a tela se contradiz.

### 🔴 Segurança — cache do Trust Score é global (cross-tenant)
- `api/routers/metrics.py:~134`: `cache_key = f"trust:{periodo}"` **sem `user.sub`** (o
  `dashboard-bundle` usa `{user.sub}:{periodo}`). Na janela de 5 min, um usuário pode receber o
  score de outra org. **Atenção dobrada** porque o RLS por `org_id` acabou de entrar em produção —
  esse cache em memória fura o isolamento.

### 🟠 UX / conteúdo
- Hierarquia: o gauge compete com (e enterra) o CTA de primeira análise no estado vazio.
- 4 badges de compliance com o mesmo verde de "conquista" — sendo que 2 são **escopo**
  ("não processa cartões", "não é IF") e 1 é **em andamento** (SOC 2).
- Busca da topbar é **`readOnly`** (campo morto) e o sino é um botão **desabilitado "em breve"**.
- "30 dias sem falha · 0 ciclos" — frase contraditória no vazio.

### 🟠 Acessibilidade (WCAG AA)
- Gauge SVG sem `role="img"`/`aria-label` (o "80" não é anunciado).
- `ProgressBar` sem `role="progressbar"`/`aria-valuenow`.
- Ícones Lucide decorativos sem `aria-hidden`; saltos de heading (`h3` sem `h2`).

### 🟠 Código / performance (`DashboardPage.tsx`)
- 5 `fetch` manuais via `useState`/`useEffect` (sem `react-query`, embora já esteja no projeto) →
  re-fetch a cada remontagem de rota; `loading` monolítico espera **até o LLM** de Insights.
- Promises rejeitadas silenciadas (sem feedback de erro).
- Charts (Recharts) importados estáticos → peso no bundle inicial.

---

## 2. Princípios do redesign (a régua dos 3 modelos)

1. **Honestidade no vazio** — sem score/100% fantasma; herói do vazio = importar extrato.
2. **Hierarquia simples** — marca/título → ação ou saúde → KPIs essenciais → 1–2 charts → atividade.
3. **Divulgação progressiva** — gráficos só quando há dados.
4. **Acessível por padrão** — aria no medidor, barras e ícones.
5. **Compliance honesto** — separar certificação real de nota de escopo; nada inflado.
6. **Zero elemento morto** — busca real (⌘K) ou nenhuma; sem botões "em breve".

---

## 3. Os três modelos (mockups HTML em `dashboard-mockups/`)

| Modelo | Conceito | Tema | Para quem |
|---|---|---|---|
| **A — Clareza** | Minimalista, onboarding-first, muito respiro (Linear/Vercel). Vazio = só a ação. | Claro | Quem quer foco e simplicidade máxima |
| **B — Cockpit** | Bento grid operacional, escaneável, mais densidade organizada (Stripe-like). | Claro | Uso diário, visão operacional |
| **C — Auditor** | "Sala de controle" navy, confiança/compliance + módulos fiscais em destaque. | Escuro | Persona auditor, percepção premium |

Cada um: reusa logo+nome+paleta, trata o vazio com honestidade, e traz um **toggle "Com dados / Sem dados"** para ver os dois estados ao vivo.

---

## 4. Roadmap de implementação (após escolher o modelo)

- **Fase 0 — Correções de verdade (independem do visual; podem ir já):**
  - Backend: `total==0` → `score=None`/`"Sem dados"` (não 80); `taxa_sucesso`/`dias_sem_falha` neutros.
  - Backend: `cache_key` do trust com `user.sub` (fecha o vazamento cross-tenant).
  - Frontend: guard `total_conciliacoes > 0` no `SecurityRing` (barras e gauge).
- **Fase 1 — Estrutura:** adotar o modelo escolhido; refatorar `DashboardPage` para `react-query`,
  loading granular (não esperar o LLM), empty-first.
- **Fase 2 — Acessibilidade:** aria no `SecurityRing`/`ProgressBar`/`KpiCard`/`Heatmap`.
- **Fase 3 — Limpeza:** command palette ⌘K (ou remover busca); redesenhar badges; remover sino morto.
- **Fase 4 — Performance:** `lazy` nos charts; tratamento de erro por slot.

> Sugestão: **Fase 0 vira um PR pequeno e imediato** (corrige o falso-positivo + o cache cross-tenant),
> e o redesign visual (Fases 1–4) segue no modelo escolhido.
