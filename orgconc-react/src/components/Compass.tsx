/** Rosa-dos-ventos minimalista (8 pontas) — decoração cartográfica. */
interface Props {
  size?: number;
  className?: string;
  spin?: boolean;
}

export function Compass({ size = 48, className = "", spin = false }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className={`text-muted-foreground ${spin ? "animate-compass-spin" : ""} ${className}`}
    >
      {/* Círculo externo */}
      <circle cx="24" cy="24" r="22" fill="none" stroke="currentColor" strokeWidth="0.6" opacity="0.5" />
      <circle cx="24" cy="24" r="16" fill="none" stroke="currentColor" strokeWidth="0.4" opacity="0.35" />
      <circle cx="24" cy="24" r="2" fill="currentColor" opacity="0.6" />

      {/* 4 pontas cardinais (preenchidas) */}
      <path d="M24 4 L26 24 L24 24 Z" fill="currentColor" opacity="0.9" />
      <path d="M24 4 L22 24 L24 24 Z" fill="currentColor" opacity="0.55" />
      <path d="M24 44 L26 24 L24 24 Z" fill="currentColor" opacity="0.55" />
      <path d="M24 44 L22 24 L24 24 Z" fill="currentColor" opacity="0.9" />
      <path d="M4 24 L24 22 L24 24 Z" fill="currentColor" opacity="0.55" />
      <path d="M4 24 L24 26 L24 24 Z" fill="currentColor" opacity="0.9" />
      <path d="M44 24 L24 22 L24 24 Z" fill="currentColor" opacity="0.9" />
      <path d="M44 24 L24 26 L24 24 Z" fill="currentColor" opacity="0.55" />

      {/* Diagonais finas */}
      <line x1="10" y1="10" x2="38" y2="38" stroke="currentColor" strokeWidth="0.4" opacity="0.4" />
      <line x1="38" y1="10" x2="10" y2="38" stroke="currentColor" strokeWidth="0.4" opacity="0.4" />

      {/* Letra N (norte) */}
      <text
        x="24"
        y="3"
        textAnchor="middle"
        fontSize="3.2"
        fontFamily="JetBrains Mono, monospace"
        fontWeight="700"
        fill="currentColor"
        opacity="0.85"
      >
        N
      </text>
    </svg>
  );
}
