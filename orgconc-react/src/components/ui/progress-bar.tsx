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
  /** Rótulo acessível — vira aria-label do progressbar (ex.: "Taxa de sucesso: 98%"). */
  label?: string;
}

/**
 * Barra de progresso horizontal: trilha + preenchimento por largura %.
 * Primitivo compartilhado (SecurityRing.Goal, AuditoriaForensePage,
 * RiscoTributarioPage). Acessível: role="progressbar" + aria-valuenow/min/max.
 */
export function ProgressBar({
  value,
  colorClass,
  size = "md",
  trackClassName = "bg-muted",
  fillClassName,
  label,
}: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className={cn("w-full overflow-hidden rounded-full", size === "sm" ? "h-1.5" : "h-2", trackClassName)}
    >
      <div
        className={cn("h-full transition-all", colorClass, fillClassName)}
        style={{ width: `${pct}%` }}
        aria-hidden="true"
      />
    </div>
  );
}
