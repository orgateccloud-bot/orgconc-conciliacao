import { cn } from "@/lib/utils";

interface ProgressBarProps {
  /** Valor 0–100; clampado internamente. */
  value: number;
  /** Classe Tailwind `bg-*` do preenchimento (cada chamador tem seu mapa de cores). */
  colorClass: string;
  /** Altura da trilha: "sm" = h-1.5 (dashboard), "md" = h-2 (padrão das páginas). */
  size?: "sm" | "md";
  /** Classe da trilha (fundo). Default `bg-muted`. */
  trackClassName?: string;
  /** Classe extra no preenchimento (ex.: "rounded-full duration-700"). */
  fillClassName?: string;
}

/**
 * Barra de progresso horizontal: trilha + preenchimento por largura %.
 * Primitivo extraído de 3 cópias idênticas (SecurityRing.Goal,
 * AuditoriaForensePage, RiscoTributarioPage). Os rótulos e os mapas de cor
 * ficam no chamador — só a mecânica trilha+fill é compartilhada aqui.
 */
export function ProgressBar({
  value,
  colorClass,
  size = "md",
  trackClassName = "bg-muted",
  fillClassName,
}: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("w-full overflow-hidden rounded-full", size === "sm" ? "h-1.5" : "h-2", trackClassName)}>
      <div
        className={cn("h-full transition-all", colorClass, fillClassName)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
