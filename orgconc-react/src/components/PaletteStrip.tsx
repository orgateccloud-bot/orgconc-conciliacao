/**
 * PaletteStrip — service cards do deck mostrando as 3 frentes
 * tonais da paleta institucional Orgatec.
 */
const ZONAS = [
  {
    num: "01",
    cat: "Institucional",
    nome: "Navy",
    hex: "#1A3A6B",
    descricao: "Tom institucional · fundamentos contábeis e relatórios formais.",
    bg: "bg-brand-navy",
    fg: "text-white",
  },
  {
    num: "02",
    cat: "Destaque",
    nome: "Blue",
    hex: "#5BA9D6",
    descricao: "Cor de destaque · CTAs, gráficos e eyebrows de seção.",
    bg: "bg-brand-blue",
    fg: "text-white",
  },
  {
    num: "03",
    cat: "Apoio",
    nome: "Azure",
    hex: "#7BC8E0",
    descricao: "Acento suave · backgrounds e ilustrações de baixo peso.",
    bg: "bg-brand-azure",
    fg: "text-brand-ink",
  },
];

export function PaletteStrip() {
  return (
    <section aria-labelledby="palette-title" className="animate-slide-up">
      <header className="flex items-baseline justify-between mb-5">
        <div className="flex items-center gap-3">
          <h2 id="palette-title" className="eyebrow">Paleta institucional</h2>
          <span className="h-px w-12 bg-border" />
        </div>
        <span className="deck-caption">3 tons · 1 marca</span>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {ZONAS.map((z) => (
          <article
            key={z.nome}
            className="group relative overflow-hidden rounded-3xl border bg-card transition-shadow hover:shadow-card-hover"
          >
            <div className={`relative h-28 ${z.bg}`}>
              <div className={`absolute top-3 left-4 ${z.fg} text-[11px] font-mono tracking-[0.22em] uppercase opacity-85`}>
                {z.num} · {z.cat}
              </div>
              <div className={`absolute bottom-3 right-4 ${z.fg} font-mono tabular-nums font-semibold opacity-95 text-sm`}>
                {z.hex}
              </div>
            </div>
            <div className="px-7 py-6 space-y-2">
              <h3 className="font-semibold text-2xl tracking-tight text-foreground">
                {z.nome}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground font-light">
                {z.descricao}
              </p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
