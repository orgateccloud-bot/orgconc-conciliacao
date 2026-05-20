/**
 * Tira de amostras de profundidade (paleta extraída do logo).
 * Cada zona é uma "camada batimétrica" com sua descrição cartográfica.
 */
const ZONAS = [
  {
    nome: "Abissal",
    profundidade: "4 000 m",
    hex: "#1E3A8A",
    var: "navy",
    descricao: "Fundamentos contábeis",
    bg: "bg-brand-navy",
    fg: "text-white",
  },
  {
    nome: "Batipelágica",
    profundidade: "200 m",
    hex: "#2563EB",
    var: "blue",
    descricao: "Operações financeiras",
    bg: "bg-brand-blue",
    fg: "text-white",
  },
  {
    nome: "Epipelágica",
    profundidade: "50 m",
    hex: "#22D3EE",
    var: "cyan",
    descricao: "Interface · superfície",
    bg: "bg-brand-cyan",
    fg: "text-brand-ink",
  },
];

export function PaletteStrip() {
  return (
    <section aria-labelledby="palette-title" className="animate-slide-up">
      <header className="flex items-baseline justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 id="palette-title" className="atlas-label">Sondagem cromática</h2>
          <span className="h-px w-12 bg-border" />
        </div>
        <span className="atlas-caption">3 zonas · 3 medições</span>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {ZONAS.map((z, i) => (
          <article
            key={z.var}
            className="relative overflow-hidden rounded-lg border bg-card shadow-card group transition-shadow hover:shadow-card-hover"
          >
            {/* Faixa de cor (oceano) */}
            <div className={`relative h-24 ${z.bg} overflow-hidden`}>
              {/* Linhas batimétricas sobre a faixa */}
              <svg
                className="absolute inset-0 w-full h-full opacity-20"
                viewBox="0 0 240 96"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path d="M0 24 Q 60 8, 120 24 T 240 24" fill="none" stroke="white" strokeWidth="0.8" />
                <path d="M0 48 Q 60 64, 120 48 T 240 48" fill="none" stroke="white" strokeWidth="0.6" opacity="0.7" />
                <path d="M0 72 Q 60 56, 120 72 T 240 72" fill="none" stroke="white" strokeWidth="0.6" opacity="0.7" />
              </svg>
              {/* Profundidade (medição em destaque) */}
              <div className={`absolute bottom-2 left-3 ${z.fg} font-mono text-[10px] tracking-[0.18em] uppercase opacity-80`}>
                Folha {String(i + 1).padStart(2, "0")}
              </div>
              <div className={`absolute top-2 right-3 ${z.fg} font-mono tabular-nums font-semibold opacity-90`}>
                {z.profundidade}
              </div>
            </div>

            {/* Metadados */}
            <div className="px-4 py-3 space-y-1.5">
              <div className="flex items-baseline justify-between">
                <h3 className="font-semibold text-foreground tracking-tight">
                  Zona {z.nome}
                </h3>
                <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                  {z.hex}
                </span>
              </div>
              <p className="text-xs text-muted-foreground leading-snug">{z.descricao}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
