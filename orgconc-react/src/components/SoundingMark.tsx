/** Marcador de coordenada — "+" estilizado de cartografia. */
interface Props {
  className?: string;
  size?: number;
  label?: string;
}

export function SoundingMark({ className = "", size = 14, label }: Props) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`} aria-hidden="true">
      <svg width={size} height={size} viewBox="0 0 14 14" className="text-muted-foreground/60">
        <line x1="7" y1="0" x2="7" y2="14" stroke="currentColor" strokeWidth="0.6" />
        <line x1="0" y1="7" x2="14" y2="7" stroke="currentColor" strokeWidth="0.6" />
        <circle cx="7" cy="7" r="1.5" fill="none" stroke="currentColor" strokeWidth="0.6" />
      </svg>
      {label && (
        <span className="text-[9px] font-mono tracking-[0.18em] uppercase text-muted-foreground/70">
          {label}
        </span>
      )}
    </span>
  );
}
