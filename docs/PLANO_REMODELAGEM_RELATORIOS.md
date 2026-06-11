# Plano de Remodelagem dos Relatórios (XLSX · HTML · PDF) — padrões modernos

> **Base:** análise multi-agente de 2026-06-11 sobre os três artefatos do Laudo
> Integrado gerados com dados reais (consolidado de 13 abas / 8 páginas), cruzada
> com o código gerador (`api/services/laudo_forense.py`) e com o design system do
> app (`orgconc-react/src/index.css`, Tailwind 4 `@theme`).
> **Regra de deploy:** PRs ficam verdes aguardando OK explícito por PR.

## Legenda
- 🤖 **Autônomo** — implementável direto (código/testes/docs).
- 🔑 **Requer owner** — decisão de negócio ou dado que só o owner tem.
- Esforço: **P** ≤ meio dia · **M** 1–2 dias · **G** 3–5 dias.

---

## Diagnóstico (resumo dos achados)

**O que já é forte:** identidade coesa nas 13 abas (constantes de estilo
reutilizáveis), capa-hub com hyperlinks, freeze panes em 100% das abas,
semântica forense (pós-baixa em alerta, Consolas p/ identificadores), valores
como números reais com `number_format`, capa editorial no HTML/PDF com selo de
natureza ("caráter indicativo").

**Problemas de severidade ALTA (atravessam os 3 formatos):**

| # | Problema | Onde |
|---|---|---|
| A1 | **3 formatos de número convivendo** — en-US (`1,234.56`) na maior parte, pt-BR nas referências legais e um híbrido inválido (`15.684.966.54`) na conformidade. Risco real de leitura errada em laudo pericial | HTML/PDF/XLSX (textos) |
| A2 | **Fontes da identidade nunca chegam ao PDF** — `@import` Google Fonts é bloqueado pelo `_block_url_fetcher` (anti-SSRF) → PDF sai em fallback de sistema | HTML→PDF |
| A3 | **Logo**: 511KB de PNG base64 (95% do peso do HTML) exibido a 52px; e na capa do PDF o `alt` vazou impresso ("ORGATEC" duplicado cortado) | HTML/PDF |
| A4 | **Sem classificação de sigilo** em documento com dados bancários reais de terceiros; CPF do sócio repetido nas 13 abas do XLSX; metadados vazios (`creator=openpyxl`), sem proteção de planilha | XLSX/PDF |
| A5 | **Textos do sistema sem acentuação** ("Sumario Executivo", "Conclusao") convivendo com dados acentuados — herança ASCII sem razão técnica (pipeline é UTF-8) | os 3 |
| A6 | **Datas gravadas como texto** no XLSX (quebra ordenação/filtro/pivot — as primeiras operações de um perito) | XLSX |
| A7 | **Sem responsável técnico** (nome/CRC/assinatura) no fechamento do laudo | PDF |
| A8 | **3 identidades visuais divergentes** — app `#1A3A6B/#5BA9D6` (Manrope/Instrument Serif), XLSX navy próprio (Calibri), PDF outro navy (fallback) — tokens hardcoded e dessincronizados em 3 lugares | os 3 |

**Médios:** zero formatação condicional nativa e zero tabelas estruturadas no
XLSX (zebra/alertas se desfazem ao ordenar); nenhum print setup (a aba de 27
colunas é inimprimível); totais estáticos sem `SUBTOTAL`; severidade indicada
só por emoji (vira hachura cinza idêntica no WeasyPrint — os 4 níveis ficam
indistinguíveis no PDF); sem TOC/âncoras; contraste AA reprovado nas barras
sólidas de severidade; truncamento cru de textos; quebras de página órfãs;
nenhum gráfico em 8 páginas (a seção "Risk Heatmap" é uma tabela).

---

## Princípios e restrições (inegociáveis)

1. **Regressão ao centavo**: a fase de CÁLCULO (`preparar_calculo_laudo`, refactor
   2.4 fases 1–3) não é tocada. Remodelagem é só RENDER. Toda fase fecha com a
   regressão golden nos dados reais — valores comparados **como conjunto**
   (layout novo = posições novas; o conjunto de valores é o invariante) e
   re-baseline documentado.
2. **WeasyPrint, sem rede**: nada de `@import`/CDN — fontes embarcadas no repo
   (`api/assets/fonts/`, WOFF2/TTF + `@font-face`); Playwright segue proibido.
3. **Uma identidade**: tokens únicos derivados do app ("Direção Leve"), nunca
   mais 3 paletas hardcoded.
4. **Cor nunca é o único portador** (WCAG 1.4.1): severidade = cor + rótulo
   textual, sempre.

---

## Fase 0 — Fundação: `report-tokens` + fontes + locale 🤖 (M)

Cria a fonte única de verdade que todas as outras fases consomem.

- **`shared/report-tokens.json`** consumido por: gerador XLSX (dict Python),
  template HTML (CSS vars) e frontend (TS). Conteúdo:
  - *Paleta núcleo (= app):* ink `#0E2A47` · ink-soft `#3F5A78` · navy `#1A3A6B`
    (headers) · blue `#5BA9D6` (acentos) · pale `#B8DDEE` · cloud `#F4F9FC`
    (zebra) · surface `#FFFFFF` · rule-solid `#DDE1E5` (flatten do hairline
    rgba p/ Excel) · neutral `#94A3B8`.
  - *Severidade WCAG AA (3 séries por nível — chip-bg / chip-text / sólido-700):*
    CRÍTICO `#FEE2E2`/`#991B1B`/`#B91C1C` · ALTO `#FFEDD5`/`#9A3412`/`#C2410C` ·
    MÉDIO `#FEF9C3`/`#854D0E`/`#A16207` · BAIXO `#DCFCE7`/`#166534`/`#15803D`
    (escala convencional vermelho/laranja/âmbar/verde — corrige o MÉDIO azul).
  - *Financeiro:* crédito `#16A34A` · débito `#DC2626` · neutro `#94A3B8`.
- **Fontes embarcadas** em `api/assets/fonts/` (TTF/WOFF2 no repo):
  Manrope (corpo/títulos), Instrument Serif (acento de capa), JetBrains Mono
  (números/identificadores) + `@font-face` no template e `url_fetcher` liberando
  apenas `file://` desses assets. Fallbacks: Segoe UI/Arial · Georgia · Consolas.
  XLSX (não embute fonte): Calibri/Aptos no corpo + Consolas nos identificadores.
- **Locale pt-BR centralizado**: helper único de formatação (`format_brl`,
  `format_num`, `format_pct` — Babel ou conversão pós-format) substituindo TODOS
  os `f"{v:,.2f}"` de `gerar_md`/render. Mata o A1 nos três formatos de uma vez.
- **Acentuação correta** em todas as strings de sistema (mata o A5).

**Aceite:** tokens consumidos pelos 3 geradores · PDF renderiza com Manrope
(provado por inspeção de fontes do arquivo) · zero `1,234.56` em qualquer
artefato · regressão golden de VALORES verde (números idênticos em pt-BR).

## Fase 1 — Credibilidade pericial (quick wins ALTOS) 🤖·🔑 (M)

- Logo: SVG inline (ou PNG ≤160px) — corta ~95% do peso do HTML e conserta o
  `alt` vazado na capa do PDF (A3).
- **Tarja de sigilo** "CONFIDENCIAL — USO RESTRITO" via CSS Paged Media em todas
  as páginas do PDF + cabeçalho do HTML + célula/cabeçalho nas abas do XLSX (A4).
  🔑 *confirmar o texto da tarja com o owner.*
- **Higiene de dados pessoais no XLSX**: CPF do sócio apenas na aba
  "2. Identificação" (sai do banner das outras 12).
- **Metadados**: title/author/subject/keywords + ID único do laudo nos 3
  formatos; XLSX com `properties` preenchidas; PDF com título UTF-8 correto.
- **Datas reais no XLSX** (datetime + `number_format dd/mm/yyyy`) — mata o A6.
- **Proteção leve do XLSX**: `sheet.protection` nas abas de laudo (sem senha
  forte — é selo de intenção e trilha, não DRM).
- **Bloco de responsável técnico** no fechamento (nome, CRC, local/data,
  campo de assinatura) — 🔑 *dados do responsável (nome/CRC) são do owner;
  layout é autônomo.*

**Aceite:** PDF com tarja em 100% das páginas · HTML ≤ 60KB · CPF em 1 aba ·
datas ordenáveis no Excel · metadados visíveis nas propriedades dos arquivos.

## Fase 2 — HTML/PDF editorial moderno 🤖 (G)

- **Capa na linguagem do app** (assinatura do HeroCard): eyebrow JetBrains Mono
  uppercase, título Manrope leve com palavra de acento em Instrument Serif
  itálico azul, caption-carimbo ("Folha I · Anno MMXXVI · vX.Y.Z").
- **Sumário executivo visual de 1 página**: 4–6 KPI-cards (volume bruto,
  múltiplo do teto, pós-baixa, retenção) + gráfico de barras da evolução mensal
  + donut da distribuição por classe — **SVG inline** (WeasyPrint renderiza
  nativamente, sem JS).
- **Severidade semafórica imprimível**: chips `.sev-*` com fundo + rótulo
  textual (substitui os emojis 🔴🟠🔵🟢 que viram hachura no PDF).
- **TOC navegável**: ids nos h2 + `<nav>`; no impresso,
  `target-counter(attr(href), page)` dá números de página automáticos.
- **Running header + paginação**: `string-set` da seção corrente no topo,
  "página X de Y" no rodapé.
- **CSS por mídia**: `@media screen` (base 16px, max-width ~80ch, dark mode via
  `prefers-color-scheme`) separado do `@media print/@page` (pt). O HTML deixa de
  ser só "pré-PDF".
- **Quebras corretas**: remover `page-break-inside: avoid` de `table` (deixar o
  thead repetir), `break-after: avoid` em headings, proteger bullets do quadro
  societário; truncamentos com reticências.
- **Microtipografia**: `font-variant-numeric: tabular-nums` nas colunas
  numéricas; `caption`/`th[scope]` nas tabelas; h1 real + landmarks (a11y).
- **Achados numerados (A-01…A-NN)** no padrão forense: tabela-resumo com ID,
  severidade, valor, critério/base legal, recomendação, referência à seção.
- **Ficha técnica final**: metodologia resumida (testes determinísticos, fontes
  OFX/RFB/BrasilAPI, limitações), glossário (EPP, MEI-TAC, pós-baixa, smurfing,
  carrossel), hash SHA-256 do conteúdo p/ verificação de integridade.

**Aceite:** PDF com fontes da marca, TOC com páginas, tarja, running header,
zero emoji, ≥2 gráficos SVG; HTML legível em tela (Lighthouse a11y ≥ 90) e
idêntico em conteúdo; regressão de VALORES verde.

## Fase 3 — XLSX moderno 🤖 (G)

- **Tabelas estruturadas (ListObjects)** nas abas de dados (Transações,
  Disposições, CNPJs, Conformidade): zebra nativa estável, filtros, referências
  estruturadas, pronto p/ Pivot/Power Query.
- **Formatação condicional nativa**: escala de cor/data bars no heatmap de
  verdade (aba 6), regras `cellIs`/`expression` para pós-baixa, BAIXADA,
  excessos MEI — o vínculo lógico sobrevive a ordenação.
- **Linha de totais com `SUBTOTAL(109,…)`** nas tabelas (reage a filtros e é
  auditável dentro do Excel) — mantendo a prova externa via regressão.
- **Print setup em 100% das abas**: orientação, `fitToWidth=1`,
  `print_title_rows` (banner+header repetem), área de impressão; a aba de 27
  colunas ganha layout imprimível.
- **Navegação de volta**: link "← Capa" em todas as abas + `tab_color` por
  grupo (operação/fiscal/conformidade).
- **Tokens da Fase 0** aplicados (navy/zebra/severidade AA) — fim da paleta
  paralela; eyebrow Consolas + título no padrão da capa do app.

**Aceite:** ordenar/filtrar não quebra zebra nem alertas · impressão da aba 5
sai paginada com cabeçalho repetido · totais respondem a filtro · regressão de
VALORES como conjunto verde + novo golden de layout documentado.

## Fase 4 — Extras de arquivamento (opcional) 🤖·🔑 (M)

- **PDF/A-2b** para arquivamento processual (WeasyPrint ≥60 suporta variantes).
- **Páginas nomeadas** (`@page portrait/landscape`): capa/conclusão em retrato,
  tabelas largas em paisagem.
- Assinatura digital ICP-Brasil do PDF — 🔑 *certificado do owner; fora do
  gerador (passo de pós-processamento)*.

---

## Sequência e verificação

| Ordem | Fase | Esf. | Gate de saída |
|---|---|---|---|
| 1 | Fase 0 (tokens+fontes+locale) | M | regressão golden (valores) + PDF com fonte embarcada |
| 2 | Fase 1 (credibilidade) | M | checklist A1–A7 fechado |
| 3 | Fase 2 (HTML/PDF) | G | aceite da fase + revisão visual do owner 🔑 |
| 4 | Fase 3 (XLSX) | G | aceite da fase + revisão visual do owner 🔑 |
| 5 | Fase 4 (opcional) | M | decisão do owner |

**Método de regressão por fase** (o mesmo do refactor 2.4): gerar baseline no
HEAD, aplicar a fase, regerar e comparar — Fase 0/1 comparam por posição;
Fases 2/3 (layout muda) comparam o **conjunto de valores numéricos** e
re-baseline com diff visual revisado. Dados reais ficam fora do repo (pasta
temporária, apagada ao fim).

**Riscos:** licenças das fontes (Manrope/JetBrains Mono OFL, Instrument Serif
OFL — ok p/ embarcar; conferir no PR) · peso do PDF com fontes embarcadas
(subset WOFF2 mitiga) · `SUBTOTAL` muda células de TOTAL de estático p/ fórmula
(a regressão de valores lê o resultado — validar com openpyxl `data_only` ou
manter valor + fórmula).
