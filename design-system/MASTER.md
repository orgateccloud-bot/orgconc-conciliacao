# Design System: OrgConc — Aurora Blue
> Atualizado em 2026-05-19 — Linguagem visual nova, baseada em ui-ux-pro-max v2.5.0

## Conceito
**Aurora Blue:** fundo claro com camadas de azul flamejante oscilando e flutuando como uma aurora. Glassmorphism nos cards, gradientes vivos nos CTAs, transparências controladas. Profissional, mas com presença sutil de movimento — para reduzir fadiga em jornadas longas (auditoria, conciliação).

## Pattern
- **Name:** Real-Time / Operations Dashboard com Aurora
- **Color Strategy:** Light mode + accent azul gradiente. Aurora animada de fundo (3 blobs azuis). Glass nos cards.
- **Sections:** Hero (Aurora ativa) → Métricas (cards glass) → Como funciona → CTA gradiente

## Style
- **Name:** Aurora Blue (Light Glass + Animated Accent)
- **Mode:** Light ✓ Full | Dark ◐ Partial (futuro)
- **Keywords:** glassmorphism, aurora, animated blobs, gradient CTAs, backdrop-filter, electric blue, fintech premium, suave
- **Best For:** Dashboards de uso prolongado, fintech, contabilidade, auditoria
- **Performance:** ⚡ Excelente (transform/opacity only) | **Acessibilidade:** WCAG AA + reduced-motion respeitado

## Colors

### Tokens base
| Role | Hex | CSS Variable |
|------|-----|--------------|
| Navy (Primary) | `#0F172A` | `--navy` |
| Blue Flamejante (CTA) | `#0052FF` | `--blue` |
| Blue Soft (gradient stop) | `#4D7CFF` | `--blue-soft` |
| Sky (gradient end) | `#0EA5E9` | `--sky` |
| Aurora-1 (blob claro) | `#93C5FD` | `--aurora-1` |
| Aurora-2 (blob médio) | `#60A5FA` | `--aurora-2` |
| Aurora-3 (blob denso) | `#3B82F6` | `--aurora-3` |
| Blue-10 (bg leve) | `#DBEAFE` | `--blue10` |
| Blue-20 (bg médio) | `#BFDBFE` | `--blue20` |

### Status
| Role | Hex | Variable |
|------|-----|----------|
| Success | `#16A34A` | `--green` |
| Destructive | `#DC2626` | `--red` |
| Warning | `#D97706` | `--orange` |
| Multi-modelo (roxo) | `#7C3AED` | `--purple` |

### Superfícies translúcidas
| Role | Valor | Variable |
|------|-------|----------|
| Background base | `#F0F7FF` | `--bg` |
| Background mesh | radial gradients DBEAFE+E0E7FF+F0F9FF | `--bg-mesh` |
| Surface (glass) | `rgba(255,255,255,.72)` | `--surface` |
| Surface solid | `#FFFFFF` | `--surface-solid` |
| Border (glass) | `rgba(186,230,253,.5)` | `--border` |
| Border solid | `#E2E8F0` | `--border-solid` |

## Gradientes oficiais
```css
/* CTA primário */
background: linear-gradient(135deg, #0052FF 0%, #4D7CFF 50%, #0EA5E9 100%);

/* Header de relatório */
background: linear-gradient(135deg, #0F172A 0%, #0B1B3D 40%, #0052FF 100%);

/* Mesh background (toda a app) */
background-image:
  radial-gradient(at 20% 10%, #DBEAFE 0%, transparent 50%),
  radial-gradient(at 80% 80%, #E0E7FF 0%, transparent 50%),
  radial-gradient(at 50% 50%, #F0F9FF 0%, transparent 60%);
```

## Typography

```css
@import url('https://fonts.googleapis.com/css2?family=Calistoga&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

| Role | Família | Peso |
|------|---------|------|
| Headings (display) | Calistoga | Regular |
| Body / UI | Inter | 300–700 |
| Dados / Código | JetBrains Mono | 400, 500 |

H1 do relatório usa **clip text com gradiente** (navy → blue) para coerência com a Aurora.

## Aurora Background (CSS)

Três blobs absolutamente posicionados oscilando em loops longos (22–32s). Respeita `prefers-reduced-motion`:

```css
.aurora { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
.aurora-blob { position: absolute; border-radius: 50%; filter: blur(80px); will-change: transform; }
.aurora-blob.b1 { /* indigo, top-left */    animation: aurora-float-1 22s ease-in-out infinite; }
.aurora-blob.b2 { /* sky, right-middle */   animation: aurora-float-2 28s ease-in-out infinite; }
.aurora-blob.b3 { /* light blue, bottom */  animation: aurora-float-3 32s ease-in-out infinite; }

@media (prefers-reduced-motion: reduce) { .aurora-blob { animation: none; } }
```

## Glass cards
```css
.card {
  background: rgba(255,255,255,.72);
  backdrop-filter: blur(18px) saturate(180%);
  -webkit-backdrop-filter: blur(18px) saturate(180%);
  border: 1px solid rgba(186,230,253,.5);
  border-radius: 14px;
  box-shadow: 0 4px 20px rgba(15,23,42,.06);
  transition: box-shadow .3s cubic-bezier(0.16, 1, 0.3, 1);
}
```

## Botão primário (gradient flamejante)
```css
.btn-primary {
  background: linear-gradient(135deg, var(--blue), var(--blue-soft) 50%, var(--sky));
  background-size: 200% 100%;
  background-position: 0% 50%;
  color: #fff;
  box-shadow: 0 6px 18px rgba(0,82,255,.28), inset 0 1px 0 rgba(255,255,255,.2);
  transition: background-position .6s, box-shadow .25s;
}
.btn-primary:hover {
  background-position: 100% 50%;
  box-shadow: 0 10px 28px rgba(0,82,255,.38), 0 0 24px rgba(77,124,255,.35);
}
```

## Spacing Scale (4pt)
```
4px · 8px · 12px · 16px · 20px · 24px · 32px · 40px · 48px · 64px
```

## Radius
- Cards / modal: `14px`
- Inputs / botões: `10px`
- Badges / pills: `999px`

## Componentes implementados (Aurora Blue)

> A UI migrou do protótipo single-file `frontend/index.html` (removido) para o
> SPA React em `orgconc-react/`. As referências abaixo apontam para a
> implementação React atual. A aurora animada agora vive no hero do Login.

| Componente | Arquivo | Aurora? |
|-----------|---------|---------|
| Dashboard principal | `orgconc-react/src/pages/DashboardPage.tsx` | ✅ |
| Sidebar gradient | `orgconc-react/src/components/Sidebar.tsx` (classe `.coastline-r`) | ✅ |
| Topbar glass | `orgconc-react/src/components/Topbar.tsx` | ✅ |
| Cards glassmorphism | `orgconc-react/src/index.css` (utility `.glass`) | ✅ |
| CTA gradient | `orgconc-react/tailwind.config.js` (`bg-brand-gradient`) | ✅ |
| Aurora blobs animados | `orgconc-react/src/pages/LoginPage.module.css` (`.auroraBand`) + `src/components/Starfield.tsx` | ✅ |
| Relatório HTML standalone | `api/main.py:_render_html()` | ✅ |
| Relatório PDF (estático) | `api/main.py:_render_pdf_html()` | ✅ (sem animação) |
| Export XLSX | `api/main.py` | ⚪ (mantém estilo Excel) |

## Print (PDF)
Quando renderizar para impressão:
- `.aurora { display: none }` — sem blobs
- `body { background: #fff }` — fundo branco
- `.wrap { background: #fff; backdrop-filter: none }` — sem glass
- `h1` volta a `color: var(--navy)` (sem clip text)
- WeasyPrint usa o mesmo HTML, gradientes radial são aceitos

## Anti-patterns (Evitar)
- Animações rápidas (< 15s loops) — quebra a sensação "suave"
- Cores de status sem contexto textual
- Glass com `backdrop-filter: blur(>30px)` (mata performance)
- Mais de 4 blobs simultâneos
- Pure black backgrounds (quebra a luminosidade da Aurora)
- Hard shadows (`0 0 0 1px`) — usar shadows difusos com low opacity

## Pre-Delivery Checklist
- [ ] Aurora visível mas não distrai (opacity 35–55%, blur ≥ 60px)
- [ ] `prefers-reduced-motion` respeitado em todos os blobs e shimmer
- [ ] Contraste de texto ≥ 4.5:1 mesmo com glass (testar com aurora ativa)
- [ ] Glass cards têm fallback (`@supports not (backdrop-filter: blur())` → background sólido)
- [ ] CTA primário tem o gradient flamejante consistente
- [ ] Hover states com `var(--easing)` cubic-bezier(0.16, 1, 0.3, 1)
- [ ] PDF print: aurora desligada, fundo branco, hierarquia preservada
- [ ] Responsivo: 375px, 768px, 1024px, 1440px
- [ ] H1 com gradient clip text não quebra impressão (fallback color)
