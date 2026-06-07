import { Target } from "lucide-react";
import type { TrustScore } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  trust: TrustScore | null;
}

export function IndicadoresGoals({ trust }: Props) {
  // Sem trust score, mostra placeholders neutros
  const taxaSucesso = trust?.breakdown.taxa_sucesso_pct ?? 0;
  const cobertura = trust?.breakdown.cobertura_pct ?? 0;
  const taxaDeteccao = trust?.metricas.taxa_anomalias_pct ?? 0;
  // Inverte: menor taxa de anomalias = barra mais alta (controle de risco melhor)
  const controleRisco = Math.max(0, 100 - taxaDeteccao);

  return (
    <div className="rounded-2xl border glass p-5">
      <div className="flex items-center gap-2 mb-4">
        <Target className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
          Indicadores
        </span>
      </div>

      <div className="space-y-3">
        <Goal label="Taxa de sucesso" valor={taxaSucesso} cor="success" sufixo="%" />
        <Goal label="Cobertura operacional" valor={cobertura} cor="primary" sufixo="%" />
        <Goal label="Controle de risco" valor={controleRisco} cor="info" sufixo="%" />
      </div>

      {!trust && (
        <p className="text-[10px] text-muted-foreground mt-3 leading-tight">
          Indicadores derivados aparecem após primeira conciliação.
        </p>
      )}
    </div>
  );
}

const COR_FILL: Record<string, string> = {
  success: "bg-green-500",
  primary: "bg-primary",
  info: "bg-cyan-500",
};

function Goal({
  label,
  valor,
  cor,
  sufixo,
}: {
  label: string;
  valor: number;
  cor: keyof typeof COR_FILL;
  sufixo: string;
}) {
  const pct = Math.max(0, Math.min(100, valor));
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-xs font-mono font-semibold tabular">
          {valor.toFixed(1)}{sufixo}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted/40 overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-700", COR_FILL[cor])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
