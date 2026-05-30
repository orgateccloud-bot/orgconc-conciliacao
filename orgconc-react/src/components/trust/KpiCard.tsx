/**
 * KpiCard — card de KPI com glassmorphism + Instrument Serif para valor.
 *
 * Migrado de frontend/dashboard_trust.html (`.kpi`, `.kpi-head`, `.kpi-value`).
 *
 * Uso:
 *   <KpiCard
 *     label="Receita conciliada"
 *     value="R$ 1.234,56"
 *     unit="BRL"
 *     icon={<TrendingUp />}
 *     delta={{ value: "+12%", direction: "up" }}
 *     foot="vs mes anterior"
 *   />
 */
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface Props {
  label: string;
  value: string | number;
  unit?: string;
  icon?: ReactNode;
  delta?: {
    value: string;                       // "+12%" ou "-3 R$"
    direction: "up" | "down" | "crit";
  };
  foot?: ReactNode;
  className?: string;
}

const PILL_CLS = {
  up:   "trust-pill-up",
  down: "trust-pill-down",
  crit: "trust-pill-crit",
} as const;

export function KpiCard({ label, value, unit, icon, delta, foot, className }: Props) {
  return (
    <div
      className={cn(
        "trust-glass rounded-2xl px-6 pt-5 pb-4",
        className,
      )}
    >
      <div className="flex items-start justify-between mb-3">
        {icon && (
          <div
            className="w-10 h-10 rounded-md flex items-center justify-center text-trust-blue bg-trust-kpi-icon"
            aria-hidden="true"
          >
            {icon}
          </div>
        )}
        {delta && (
          <span className={cn("trust-pill", PILL_CLS[delta.direction])}>
            {delta.value}
          </span>
        )}
      </div>

      <div className="trust-label mb-2">{label}</div>

      <div className="trust-num text-[2.3rem] text-foreground">
        {value}
        {unit && (
          <span className="ml-1 text-base font-medium text-muted-foreground font-sans">
            {unit}
          </span>
        )}
      </div>

      {foot && (
        <div className="mt-2 pt-2 border-t border-border flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
          {foot}
        </div>
      )}
    </div>
  );
}
