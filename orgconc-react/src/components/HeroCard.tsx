import { Logo } from "@/components/Logo";
import { APP_VERSION } from "@/lib/version";

interface Props {
  eyebrow?: string;
  title: string;
  titleAccent?: string;
  subtitle?: string;
}

export function HeroCard({ eyebrow, title, titleAccent, subtitle }: Props) {
  return (
    <section
      className="relative overflow-hidden rounded-2xl border glass px-8 py-10 lg:px-12 lg:py-12 animate-slide-up"
      aria-labelledby="hero-title"
    >
      {/* Glow sutil direita */}
      <div
        className="absolute -right-28 -top-28 h-80 w-80 rounded-full blur-3xl opacity-25 pointer-events-none"
        style={{ background: "radial-gradient(circle, #5BA9D6 0%, transparent 65%)" }}
        aria-hidden="true"
      />
      {/* Linha de costa inferior */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px opacity-40 pointer-events-none coastline-b"
        aria-hidden="true"
      />

      <div className="relative grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-10 items-center">
        <div className="space-y-3">
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
          <div className="flex items-center gap-3 pt-2">
            <span className="deck-caption">Folha I</span>
            <span className="h-px flex-1 max-w-[120px] bg-border" />
            <span className="deck-caption">Anno MMXXVI · v{APP_VERSION}</span>
          </div>
        </div>

        {/* Logo */}
        <div className="hidden lg:flex items-center justify-center shrink-0">
          <div className="relative h-28 w-28 rounded-2xl bg-brand-gradient p-4 shadow-xl flex items-center justify-center">
            {/* Brilho no canto superior direito */}
            <div
              className="absolute top-2 right-2 h-8 w-8 rounded-full blur-md opacity-40"
              style={{ background: "rgba(255,255,255,0.5)" }}
              aria-hidden="true"
            />
            <Logo size={80} />
          </div>
        </div>
      </div>
    </section>
  );
}
