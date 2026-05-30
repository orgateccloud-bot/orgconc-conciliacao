# Migração do Trust Design — dashboard_trust.html → React

> **Origem:** `frontend/dashboard_trust.html` (legado, ~5800 linhas, marcado deprecated)
> **Destino:** `orgconc-react/src/components/trust/*` + tokens em `tailwind.config.js`
> **Objetivo:** trazer a estética "bank-grade" do legado para o React **sem substituir** o sistema "Direção Leve" já existente.

---

## 1. O que mudou (resumo)

### Arquivos novos
```
orgconc-react/src/components/trust/
├── index.ts          # Facade
├── AuroraBg.tsx      # Blobs aurora animados (background da page)
├── KpiCard.tsx       # Card de KPI glass + Instrument Serif
└── Panel.tsx         # Container glass refinado
```

### Arquivos alterados (aditivos — sem quebra)
- `orgconc-react/tailwind.config.js`
  - **Adicionou** `colors.trust.*` (navy, blue, sky, aurora-1/2/3, blue-10/20)
  - **Adicionou** `backgroundImage.trust-mesh`, `trust-kpi-icon`, `trust-edge`
  - **Adicionou** `keyframes` + `animation` para `aurora-drift-1/2`
- `orgconc-react/src/index.css`
  - **Adicionou** bloco "TRUST DESIGN SYSTEM" no final com classes utilitárias `.trust-glass`, `.trust-num`, `.trust-label`, `.trust-pill*`, `.trust-active-rail`

Nada foi removido. A paleta "Direção Leve" (`brand-*`, `--d-*`) segue intacta.

---

## 2. Comparativo das duas paletas (convivem)

| Token | Direção Leve (atual) | Trust (migrado) | Uso recomendado |
|---|---|---|---|
| Navy primário | `#1A3A6B` | `#0F172A` | Direção: institucional macio · Trust: mais sério |
| Blue accent | `#5BA9D6` | `#0052FF` | Direção: céu calmo · Trust: fintech moderno |
| Sky | `#7BC8E0` | `#0EA5E9` | — |
| BG page | `#EAF4FA` | `#F0F7FF` + mesh | Trust traz radial gradients |
| Glass | `blur(14px)` | `blur(24px) saturate(180%)` + edge gradient | Trust é mais rico |
| Numeral KPI | `font-sans` (Manrope) | `font-serif` (Instrument Serif) | Trust dá um tom "auditoria" |

**Diretriz pragmática:**
- **Login, Dashboard, Relatórios:** use Trust (mais credibilidade, faz justiça ao "auditoria fiscal")
- **Configurações, Clientes (CRUD):** mantenha shadcn padrão + Direção Leve (ergonomia)

---

## 3. Como usar (3 receitas)

### 3.1 Aurora background numa página

```tsx
import { AuroraBg } from "@/components/trust";

export function DashboardPage() {
  return (
    <>
      <AuroraBg />
      <div className="relative z-10 ...">
        {/* conteúdo */}
      </div>
    </>
  );
}
```

### 3.2 Grid de KPIs

```tsx
import { KpiCard } from "@/components/trust";
import { TrendingUp, AlertTriangle, FileCheck, Activity } from "lucide-react";

<div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
  <KpiCard
    label="Conciliados"
    value="1.234"
    icon={<FileCheck className="h-5 w-5" />}
    delta={{ value: "+12%", direction: "up" }}
    foot="vs mês anterior"
  />
  <KpiCard
    label="Anomalias"
    value="23"
    icon={<AlertTriangle className="h-5 w-5" />}
    delta={{ value: "+3", direction: "crit" }}
    foot={<span>Críticas: <strong className="text-foreground">5</strong></span>}
  />
  <KpiCard
    label="Volume"
    value="R$ 458,2"
    unit="mi"
    icon={<TrendingUp className="h-5 w-5" />}
    delta={{ value: "+8%", direction: "up" }}
  />
  <KpiCard
    label="Atividade"
    value="99,8%"
    icon={<Activity className="h-5 w-5" />}
    foot="SLA do mês"
  />
</div>
```

### 3.3 Painel com título + ação

```tsx
import { Panel } from "@/components/trust";
import { Button } from "@/components/ui/button";

<Panel
  title="Últimas conciliações"
  subtitle="14 processadas hoje"
  action={<Button size="sm" variant="outline">Ver tudo</Button>}
>
  <table className="w-full">...</table>
</Panel>
```

### 3.4 Sidebar com rail ativo (estilo legado)

```tsx
// Em Sidebar.tsx, no item ativo:
<NavLink
  to="/conciliacao"
  className={({ isActive }) =>
    cn("relative px-4 py-2 rounded-md", isActive && "trust-active-rail")
  }
>
  Conciliação
</NavLink>
```

---

## 4. Tokens disponíveis

### Tailwind (`trust-*`)
```
text-trust-navy  text-trust-blue  text-trust-sky
bg-trust-navy   bg-trust-blue-10  bg-trust-blue-20  bg-trust-bg
bg-trust-mesh   bg-trust-kpi-icon  bg-trust-edge
border-trust-blue
```

### CSS classes utilitárias (em `index.css`)
```
trust-glass         → cartão glass refinado
trust-num           → numeral Instrument Serif
trust-label         → label uppercase mono curto
trust-pill          → pill base (combine com -up/-down/-crit)
trust-pill-up       → verde (DCFCE7/16A34A)
trust-pill-down     → âmbar (FEF3C7/D97706)
trust-pill-crit     → vermelho (FEE2E2/DC2626)
trust-active-rail   → barra 3px lateral (use em `position: relative`)
```

### Animações
```
animate-aurora-drift-1   → 24s drift sutil
animate-aurora-drift-2   → 30s drift inverso
```

---

## 5. Roadmap de adoção (sugestão sem urgência)

| Sprint | Ação | Esforço |
|---|---|---|
| Imediato | Aplicar `AuroraBg` + 4 `KpiCard` no `DashboardPage` | XS |
| Próximo | `Panel` envolve listagens de Conciliações e Anomalias | S |
| Próximo+ | `LoginPage` ganha `AuroraBg` + cartão `trust-glass` | S |
| Quando der | `Sidebar` ativo com `trust-active-rail` | XS |
| Opcional | Page Relatórios usa Trust completo | M |

**Não migrar:**
- Forms (Clientes CRUD): shadcn padrão dá melhor UX form
- Configurações: idem
- Tabelas densas: shadcn `<Table>` segue OK

---

## 6. O que NÃO foi migrado (de propósito)

| Do legado | Por quê |
|---|---|
| Chart.js | React já usa `recharts` (mais idiomático) |
| `omelette-injected` scripts | Runtime do Claude.ai artifact; irrelevante fora do chat |
| Layout 260-1-320 fixed grid | Conflita com layout do React (Sidebar + Outlet + Topbar) |
| `data-theme="light"` attr | Usamos `dark:` class do Tailwind |
| Fontes via `<link>` HTML | Já importadas em `index.css` no React |

---

## 7. Compatibilidade

- ✅ Dark mode: tokens `trust-*` se adaptam via `data-theme=dark` e `.dark` (Tailwind `dark:` funciona)
- ✅ `prefers-reduced-motion`: as animações aurora respeitam o bloco já existente em `index.css`
- ✅ shadcn/ui: convive — `KpiCard` e `Panel` não conflitam com `Card`, `Sheet`, etc.

---

## 8. Referências

- Origem: `frontend/dashboard_trust.html` (`/* TRUST DESIGN SYSTEM */` linha 17)
- Sistema atual: `orgconc-react/src/index.css` (Direção Leve + glassmorphism)
- shadcn/ui: `orgconc-react/src/components/ui/*`
- Análise visual: `analise_camadas_arquitetura.md` § 5.2 (Apresentação Web)
