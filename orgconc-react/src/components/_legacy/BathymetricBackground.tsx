/**
 * Fundo batimétrico — padrão SVG de linhas onduladas (curvas de profundidade)
 * sutilmente animado horizontalmente. Reage ao tema via `currentColor`.
 */
export function BathymetricBackground() {
  return (
    <div
      className="fixed inset-0 -z-10 pointer-events-none overflow-hidden text-primary"
      aria-hidden="true"
    >
      <svg
        className="absolute inset-0 w-[calc(100%+240px)] h-full opacity-[0.05] dark:opacity-[0.08] animate-wave-flow"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern
            id="bathy"
            width="240"
            height="120"
            patternUnits="userSpaceOnUse"
          >
            {/* 3 contornos batimétricos, frequências distintas */}
            <path
              d="M0 30 Q 60 10, 120 30 T 240 30"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.7"
            />
            <path
              d="M0 60 Q 60 80, 120 60 T 240 60"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.5"
              opacity="0.7"
            />
            <path
              d="M0 90 Q 60 70, 120 90 T 240 90"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.5"
              opacity="0.7"
            />
            <path
              d="M0 15 Q 60 35, 120 15 T 240 15"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.3"
              opacity="0.5"
            />
            <path
              d="M0 105 Q 60 95, 120 105 T 240 105"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.3"
              opacity="0.5"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#bathy)" />
      </svg>
      {/* Gradiente vertical de profundidade (overlay sutil) */}
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-background/50 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-primary/[0.04] to-transparent" />
    </div>
  );
}
