import { Logo } from "@/components/Logo";
import { Compass } from "@/components/Compass";
import { DepthLegend } from "@/components/DepthLegend";
import { SoundingMark } from "@/components/SoundingMark";

interface Props {
  title: string;
  subtitle?: string;
}

/**
 * Hero card — composição cartográfica do conceito "Atlas Hidrográfico":
 * logo dentro de uma "carta marítima" com contornos batimétricos
 * concêntricos, legenda de profundidade, rosa-dos-ventos e
 * marcações de coordenadas.
 */
export function HeroCard({ title, subtitle }: Props) {
  return (
    <section
      className="relative overflow-hidden rounded-xl border bg-card shadow-card animate-slide-up"
      aria-labelledby="hero-title"
    >
      {/* Background batimétrico interno (concêntrico) */}
      <svg
        className="absolute inset-0 w-full h-full text-primary opacity-[0.08]"
        viewBox="0 0 800 320"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          <radialGradient id="hero-fade" cx="20%" cy="50%" r="80%">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.6" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </radialGradient>
        </defs>
        {/* Curvas concêntricas (linhas de profundidade ao redor do logo) */}
        {[40, 70, 105, 145, 190, 240, 295].map((r, i) => (
          <ellipse
            key={r}
            cx="160"
            cy="160"
            rx={r}
            ry={r * 0.85}
            fill="none"
            stroke="currentColor"
            strokeWidth={0.6}
            opacity={1 - i * 0.1}
          />
        ))}
        <rect width="100%" height="100%" fill="url(#hero-fade)" />
      </svg>

      {/* Marcadores de coordenadas nos cantos */}
      <SoundingMark className="absolute top-3 left-3" label="01°N" />
      <SoundingMark className="absolute top-3 right-3" label="07°W" />
      <SoundingMark className="absolute bottom-3 left-3" label="03°S" />
      <SoundingMark className="absolute bottom-3 right-3" label="09°E" />

      {/* Conteúdo */}
      <div className="relative grid grid-cols-1 lg:grid-cols-[auto_1fr_auto] gap-8 lg:gap-12 items-center p-8 lg:p-12">
        {/* Logo central com moldura gradiente */}
        <div className="relative shrink-0">
          <div className="absolute -inset-4 rounded-full bg-gradient-to-br from-brand-navy via-brand-blue to-brand-cyan opacity-20 blur-xl" />
          <div className="relative h-24 w-24 lg:h-28 lg:w-28 rounded-2xl bg-brand-gradient p-4 shadow-xl flex items-center justify-center">
            <Logo size={72} />
          </div>
        </div>

        {/* Título + caption */}
        <div className="space-y-3 min-w-0">
          <div className="atlas-caption">Batimetria · ORGATEC · Anno MMXXVI</div>
          <h1
            id="hero-title"
            className="text-3xl lg:text-4xl font-bold tracking-tight text-foreground leading-[1.05]"
          >
            {title}
          </h1>
          {subtitle && (
            <p className="text-sm text-muted-foreground max-w-prose leading-relaxed">
              {subtitle}
            </p>
          )}
          <div className="flex items-center gap-3 pt-2">
            <span className="atlas-label">Folha I</span>
            <span className="h-px flex-1 max-w-[120px] bg-gradient-to-r from-border to-transparent" />
            <span className="atlas-caption opacity-70">Sondagem · v0.5.0</span>
          </div>
        </div>

        {/* Coluna direita: rosa-dos-ventos + legenda de profundidade */}
        <div className="hidden lg:flex flex-col items-end gap-6 shrink-0">
          <Compass size={56} spin />
          <DepthLegend />
        </div>
      </div>

      {/* Linha de base (escala) */}
      <div className="relative border-t bg-secondary/30 px-6 py-2.5">
        <div className="flex items-center justify-between atlas-caption">
          <span>Escala 1 : 25 000</span>
          <span className="opacity-60">Projeção Mercator · Latitude Coordenada Bancária</span>
          <span>Datum WGS-ORGATEC</span>
        </div>
      </div>
    </section>
  );
}
