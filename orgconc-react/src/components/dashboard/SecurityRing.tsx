import { ShieldCheck } from "lucide-react";
import type { TrustScore } from "@/lib/api";
import { ProgressBar } from "@/components/ui/progress-bar";

interface Props {
  data: TrustScore | null;
  loading?: boolean;
}

const RAIO = 65;
const CIRCUNFERENCIA = 2 * Math.PI * RAIO;

// Bloco ÚNICO do Trust Score: gauge + descrição + indicadores derivados.
// Consolida o que antes estava espalhado em TrustGrid + SecurityRing +
// IndicadoresGoals (os três liam o mesmo TrustScore e repetiam os números).
export function SecurityRing({ data, loading }: Props) {
  // "Sem dados" cobre data nula (carregando) E conta zerada (backend devolve
  // total_conciliacoes=0). Sem este guard, taxa de sucesso/controle de risco
  // apareceriam como 0%/100% (vácuos) num dashboard sem nenhum ciclo.
  const semDados = !data || data.metricas.total_conciliacoes === 0;
  const vazio = loading || semDados;
  const score = data && !semDados ? Math.round(data.score) : 0;
  const corStroke = corPorScore(score);
  const dashOffset = CIRCUNFERENCIA - (score / 100) * CIRCUNFERENCIA;

  const taxaSucesso = data && !semDados ? data.breakdown.taxa_sucesso_pct : 0;
  const cobertura = data && !semDados ? data.breakdown.cobertura_pct : 0;
  // Menor taxa de anomalias = controle de risco melhor (barra mais alta).
  const controleRisco = data && !semDados ? Math.max(0, 100 - data.metricas.taxa_anomalias_pct) : 0;

  return (
    <div className="rounded-3xl border glass p-6 flex flex-col md:flex-row gap-6 items-center">
      {/* Gauge */}
      <div className="relative shrink-0">
        <svg viewBox="0 0 150 150" className="w-36 h-36 -rotate-90">
          <circle cx="75" cy="75" r={RAIO} fill="none" stroke="hsl(var(--muted))" strokeWidth="10" opacity="0.4" />
          <circle
            cx="75"
            cy="75"
            r={RAIO}
            fill="none"
            stroke={corStroke}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={CIRCUNFERENCIA}
            strokeDashoffset={vazio ? CIRCUNFERENCIA : dashOffset}
            style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.16,1,0.3,1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold font-jakarta tabular leading-none">
            {vazio ? "—" : score}
          </span>
          <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-1">
            {vazio ? "Sem dados" : "Score"}
          </span>
        </div>
      </div>

      {/* Descrição + indicadores derivados */}
      <div className="flex-1 min-w-0 w-full text-center md:text-left">
        <div className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-widest text-muted-foreground mb-2">
          <ShieldCheck className="h-3 w-3" />
          Trust Score
        </div>
        <h3 className="text-lg font-semibold mb-1 leading-tight">
          {data?.descricao ?? "Calculando indicadores…"}
        </h3>
        {data && !semDados ? (
          <p className="text-xs text-muted-foreground mb-4">
            <span className="font-mono">{data.breakdown.dias_sem_falha}</span> dias sem falha ·{" "}
            <span className="font-mono">{data.metricas.total_conciliacoes}</span> ciclos em {data.periodo_dias}d
          </p>
        ) : (
          <p className="text-xs text-muted-foreground mb-4">
            Indicadores aparecem após a primeira conciliação.
          </p>
        )}

        <div className="space-y-2.5">
          <Goal label="Taxa de sucesso" valor={taxaSucesso} cor="success" />
          <Goal label="Cobertura operacional" valor={cobertura} cor="primary" />
          <Goal label="Controle de risco" valor={controleRisco} cor="info" />
        </div>
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

// Sem anotação Record<string,string> de propósito: deixa `keyof typeof COR_FILL`
// inferir a união literal ("success"|"primary"|"info") e travar o tipo de `cor`.
const COR_FILL = {
  success: "bg-green-500",
  primary: "bg-primary",
  info: "bg-cyan-500",
};

function Goal({ label, valor, cor }: { label: string; valor: number; cor: keyof typeof COR_FILL }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-xs font-mono font-semibold tabular">{valor.toFixed(1)}%</span>
      </div>
      <ProgressBar
        value={valor}
        colorClass={COR_FILL[cor]}
        size="sm"
        trackClassName="bg-muted/40"
        fillClassName="rounded-full duration-700"
      />
    </div>
  );
}
