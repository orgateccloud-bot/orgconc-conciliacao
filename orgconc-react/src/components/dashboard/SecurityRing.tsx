import { ShieldCheck } from "lucide-react";
import type { TrustScore } from "@/lib/api";

interface Props {
  data: TrustScore | null;
  loading?: boolean;
}

const RAIO = 65;
const CIRCUNFERENCIA = 2 * Math.PI * RAIO;

export function SecurityRing({ data, loading }: Props) {
  const score = data?.score ?? 0;
  const corStroke = corPorScore(score);
  const dashOffset = CIRCUNFERENCIA - (score / 100) * CIRCUNFERENCIA;

  return (
    <div className="rounded-3xl border glass p-6 flex flex-col md:flex-row gap-6 items-center">
      {/* Ring */}
      <div className="relative shrink-0">
        <svg viewBox="0 0 150 150" className="w-36 h-36 -rotate-90">
          <circle
            cx="75"
            cy="75"
            r={RAIO}
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth="10"
            opacity="0.4"
          />
          <circle
            cx="75"
            cy="75"
            r={RAIO}
            fill="none"
            stroke={corStroke}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={CIRCUNFERENCIA}
            strokeDashoffset={loading ? CIRCUNFERENCIA : dashOffset}
            style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.16,1,0.3,1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold font-jakarta tabular leading-none">
            {loading ? "—" : score}
          </span>
          <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-1">
            Score
          </span>
        </div>
      </div>

      {/* Texto */}
      <div className="flex-1 min-w-0 text-center md:text-left">
        <div className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-widest text-muted-foreground mb-2">
          <ShieldCheck className="h-3 w-3" />
          Trust Score
        </div>
        <h3 className="text-lg font-semibold mb-1.5 leading-tight">
          {data?.descricao ?? "Calculando indicadores…"}
        </h3>
        {data && (
          <div className="text-xs text-muted-foreground space-y-0.5">
            <div>
              <span className="font-mono">{data.breakdown.taxa_sucesso_pct}%</span> de conciliações sem anomalias
            </div>
            <div>
              <span className="font-mono">{data.breakdown.dias_sem_falha}</span> dias desde última falha registrada
            </div>
            <div>
              <span className="font-mono">{data.metricas.total_conciliacoes}</span> ciclos auditados em {data.periodo_dias} dias
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function corPorScore(score: number): string {
  if (score >= 90) return "#16a34a"; // verde
  if (score >= 75) return "hsl(var(--primary))";
  if (score >= 50) return "#f59e0b"; // amber
  return "#dc2626"; // vermelho
}
