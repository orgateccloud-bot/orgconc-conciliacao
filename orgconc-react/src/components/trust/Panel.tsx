/**
 * Panel — container glass refinado para sessoes da pagina.
 *
 * Migrado de frontend/dashboard_trust.html (`.panel`).
 * Equivalente trust ao Card do shadcn, com edge gradient e blur saturado.
 *
 * Uso:
 *   <Panel title="Anomalias detectadas" subtitle="Ultimas 24h">
 *     ...conteudo...
 *   </Panel>
 */
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface Props {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;          // botao/link no canto direito
  className?: string;
  children: ReactNode;
}

export function Panel({ title, subtitle, action, className, children }: Props) {
  return (
    <section className={cn("trust-glass rounded-2xl p-6", className)}>
      {(title || subtitle || action) && (
        <header className="flex items-start justify-between mb-4 gap-4">
          <div className="min-w-0">
            {title && (
              <h2 className="text-base font-semibold text-foreground leading-tight">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
