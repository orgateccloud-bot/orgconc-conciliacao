import { Logo } from "@/components/Logo";

interface Props {
  eyebrow?: string;
  title: string;
  titleAccent?: string;
  subtitle?: string;
}

/**
 * HeroCard — padrão capa do deck "Direção Leve":
 * Eyebrow mono + h1 ultra-light Manrope com acento serif italic + lead.
 * Logo Orgatec no canto direito com gradiente brand discreto atrás.
 */
export function HeroCard({ eyebrow, title, titleAccent, subtitle }: Props) {
  return (
    <section
      className="relative overflow-hidden rounded-2xl border bg-card px-8 py-12 lg:px-14 lg:py-16 animate-slide-up"
      aria-labelledby="hero-title"
    >
      {/* Glow sutil de fundo */}
      <div
        className="absolute -right-32 -top-32 h-96 w-96 rounded-full blur-3xl opacity-30 pointer-events-none"
        style={{ background: "radial-gradient(circle, #5BA9D6 0%, transparent 70%)" }}
        aria-hidden="true"
      />

      <div className="relative grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-12 items-center">
        <div className="space-y-4">
          {eyebrow && (
            <div className="eyebrow">{eyebrow}</div>
          )}
          <h1 id="hero-title" className="h1">
            {title}{" "}
            {titleAccent && <em>{titleAccent}</em>}
          </h1>
          {subtitle && (
            <p className="text-base lg:text-lg text-muted-foreground max-w-prose leading-relaxed font-light">
              {subtitle}
            </p>
          )}
          <div className="flex items-center gap-3 pt-3">
            <span className="deck-caption">Folha I</span>
            <span className="h-px flex-1 max-w-[140px] bg-border" />
            <span className="deck-caption">Anno MMXXVI · v0.5.0</span>
          </div>
        </div>

        {/* Logo no canto direito */}
        <div className="hidden lg:flex items-center justify-center shrink-0">
          <div className="relative h-32 w-32 rounded-2xl bg-brand-gradient p-5 shadow-xl flex items-center justify-center">
            <Logo size={88} />
          </div>
        </div>
      </div>
    </section>
  );
}
