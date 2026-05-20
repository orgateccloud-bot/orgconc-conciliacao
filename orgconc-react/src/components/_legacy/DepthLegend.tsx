/** Legenda batimétrica vertical — escala de profundidade com marcas. */
interface Props {
  className?: string;
}

const NIVEIS = [
  { profundidade: "0 m",     label: "Superfície" },
  { profundidade: "50 m",    label: "Epipelágico" },
  { profundidade: "200 m",   label: "Batipelágico" },
  { profundidade: "4 000 m", label: "Abissal" },
];

export function DepthLegend({ className = "" }: Props) {
  return (
    <div className={`flex items-stretch gap-3 ${className}`} aria-hidden="true">
      {/* Barra de gradient + tick marks */}
      <div className="relative w-1.5 rounded-full bg-gradient-to-b from-brand-cyan via-brand-blue to-brand-navy">
        {NIVEIS.map((_, i) => (
          <span
            key={i}
            className="absolute -left-1 w-3.5 h-px bg-foreground/60"
            style={{ top: `${(i / (NIVEIS.length - 1)) * 100}%` }}
          />
        ))}
      </div>
      {/* Labels de nível */}
      <div className="flex flex-col justify-between text-[10px] font-mono tracking-[0.12em] uppercase text-muted-foreground py-px">
        {NIVEIS.map((n) => (
          <div key={n.profundidade} className="flex items-baseline gap-1.5 leading-none">
            <span className="text-foreground/80 tabular-nums">{n.profundidade}</span>
            <span className="opacity-60">{n.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
