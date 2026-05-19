# Design System: OrgConc
> Gerado por ui-ux-pro-max v2.5.0 — B2B Accounting Reconciliation SaaS Dashboard

## Pattern
- **Name:** Real-Time / Operations Dashboard
- **Color Strategy:** Light mode, navy/blue profissional. Status colors (green/amber/red). Data-denso mas escaneável.
- **Sections:** Hero (produto + status ao vivo) → Métricas → Como funciona → CTA

## Style
- **Name:** Flat Design
- **Mode:** Light ✓ Full | Dark ✓ Full
- **Keywords:** 2D, minimalista, cores sólidas, sem sombras, linhas limpas, tipografia focada, moderno, icon-heavy
- **Best For:** Web apps, SaaS, dashboards, corporativo, B2B
- **Performance:** Excelente | **Acessibilidade:** WCAG AAA

## Colors

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#0F172A` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#334155` | `--color-secondary` |
| Accent/CTA | `#0369A1` | `--color-accent` |
| Background | `#F8FAFC` | `--color-background` |
| Foreground | `#020617` | `--color-foreground` |
| Muted | `#E8ECF1` | `--color-muted` |
| Border | `#E2E8F0` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| Success | `#16A34A` | `--color-success` |
| Warning | `#D97706` | `--color-warning` |
| Purple (Multi-modelo) | `#7C3AED` | `--color-purple` |
| Ring/Focus | `#0F172A` | `--color-ring` |

> **Notas:** Navy profissional + CTA azul. Evitar gradientes AI (purple/pink).

## Typography

```css
@import url('https://fonts.googleapis.com/css2?family=Calistoga:ital@0;1&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

| Role | Família | Peso |
|------|---------|------|
| Headings | Calistoga | Regular / Italic |
| Body / UI | Inter | 300–700 |
| Dados / Código | JetBrains Mono | 400, 500 |

- **Mood:** SaaS, fintech, editorial, bold, premium, calor humano
- **Base:** 16px | Line-height: 1.6 | Body: Inter 400

## Key Effects
- Sem gradientes / sem sombras pesadas
- Hover: mudança de cor/opacidade (150–200ms ease)
- Transições limpas: `transition: all 150ms ease`
- Ícones: SVG Heroicons/Lucide (nunca emoji)
- `border-radius: 8px` (cards), `6px` (botões), `50%` (badges circulares)

## Spacing Scale (4pt)
```
4px · 8px · 12px · 16px · 20px · 24px · 32px · 40px · 48px · 64px
```

## Componentes já implementados

| Componente | Arquivo | Status |
|-----------|---------|--------|
| Dashboard principal | `frontend/index.html` | ✅ |
| Cards de modo (Python/Sonnet/Multi) | `frontend/index.html` | ✅ |
| Drag-and-drop upload | `frontend/index.html` | ✅ |
| KPI cards | `frontend/index.html` | ✅ |
| Tabela de clientes | `frontend/index.html` | ✅ |
| Modal de cadastro | `frontend/index.html` | ✅ |
| Toast notifications | `frontend/index.html` | ✅ |
| Export XLSX estilizado | `api/main.py` | ✅ |

## Anti-patterns (Evitar)
- Animações excessivas
- Dark mode como padrão
- Gradientes AI (purple/pink)
- Emoji como ícones
- Sombras pesadas (`box-shadow` além de `0 1px 3px`)
- Cores de status sem contexto textual (só cor)

## Pre-Delivery Checklist
- [ ] Sem emojis como ícones (usar SVG: Heroicons/Lucide)
- [ ] `cursor-pointer` em todos os elementos clicáveis
- [ ] Hover states com transições suaves (150–300ms)
- [ ] Contraste de texto ≥ 4.5:1 (light mode)
- [ ] Focus states visíveis para navegação por teclado
- [ ] `prefers-reduced-motion` respeitado
- [ ] Responsivo: 375px, 768px, 1024px, 1440px
