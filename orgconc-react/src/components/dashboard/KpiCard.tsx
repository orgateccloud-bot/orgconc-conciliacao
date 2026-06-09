import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string | number;
  desc?: string;
  delta?: number | null;        // percentual; null = sem comparação disponível
  icon: LucideIcon;
  accent: "primary" | "blue" | "orange" | "green";
  /** Se true, inverte semântica do delta (subida = ruim). Usado para Anomalias. */
  inverso?: boolean;
}

const ACCENT_STYLES: Record<Props["accent"], { bar: string; iconBg: string }> = {
  primary: { bar: "bg-primary",     iconBg: "bg-primary/10 text-primary" },
  blue:    { bar: "bg-blue-400",    iconBg: "bg-blue-100 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400" },
  orange:  { bar: "bg-orange-400",  iconBg: "bg-orange-50 text-orange-500 dark:bg-orange-950/40 dark:text-orange-400" },
  green:   { bar: "bg-green-500",   iconBg: "bg-green-50 text-green-600 dark:bg-green-950/40 dark:text-green-400" },
};

export function KpiCard({ label, value, desc, delta, icon: Icon, accent, inverso }: Props) {
  const a = ACCENT_STYLES[accent];

  return (
    <div className="relative overflow-hidden rounded-2xl border glass p-5 hover:shadow-card-hover transition-all">
      <div className={cn("absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl", a.bar)} />
      <div className="flex items-start justify-between mb-3">
        <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <div className={cn("rounded-lg p-1.5", a.iconBg)}>
          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        </div>
      </div>
      <p className="text-3xl font-bold font-jakarta tracking-tight leading-none tabular">
        {value}
      </p>
      <div className="mt-2 flex items-baseline gap-2 min-h-[1rem]">
        <Delta value={delta} inverso={inverso} />
        {desc && <span className="text-xs text-muted-foreground">{desc}</span>}
      </div>
    </div>
  );
}

function Delta({ value, inverso }: { value: number | null | undefined; inverso?: boolean }) {
  if (value === null || value === undefined) return null;
  if (value === 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-muted-foreground">
        <Minus className="h-3 w-3" aria-hidden="true" />
        <span className="sr-only">estável: </span>0%
      </span>
    );
  }
  const positivo = value > 0;
  // inverso: ex.Anomalias — subir é ruim
  const bom = inverso ? !positivo : positivo;
  const Icon = positivo ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-[11px] font-semibold",
        bom ? "text-green-600 dark:text-green-400" : "text-orange-500 dark:text-orange-400"
      )}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      <span className="sr-only">{positivo ? "aumento de " : "queda de "}</span>
      {Math.abs(value).toFixed(1)}%
    </span>
  );
}
