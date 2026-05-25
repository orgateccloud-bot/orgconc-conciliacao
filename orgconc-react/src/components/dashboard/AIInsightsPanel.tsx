import { AlertTriangle, CheckCircle2, Info, RefreshCw, Sparkles } from "lucide-react";
import type { AiInsight, AiInsightsResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  data: AiInsightsResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

const TIPO_ICONE: Record<AiInsight["tipo"], { Icon: typeof Info; cor: string; bg: string }> = {
  success: { Icon: CheckCircle2,  cor: "text-green-600 dark:text-green-400",  bg: "bg-green-50 dark:bg-green-950/40" },
  warn:    { Icon: AlertTriangle, cor: "text-orange-600 dark:text-orange-400", bg: "bg-orange-50 dark:bg-orange-950/40" },
  info:    { Icon: Info,          cor: "text-blue-600 dark:text-blue-400",   bg: "bg-blue-50 dark:bg-blue-950/40" },
};

export function AIInsightsPanel({ data, loading, onRefresh }: Props) {
  return (
    <div className="rounded-3xl border glass p-6">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Insights da IA</h3>
        {data && (
          <span
            className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground"
            title={data.from_cache ? `Em cache desde ${new Date(data.gerado_em).toLocaleString("pt-BR")}` : "Recém-gerado"}
          >
            {data.from_cache ? "cache" : "novo"}
          </span>
        )}
        <button
          onClick={onRefresh}
          disabled={loading}
          className="ml-auto inline-flex items-center gap-1.5 rounded-md border bg-secondary hover:bg-muted px-2.5 py-1 text-[11px] font-medium transition-colors disabled:opacity-50"
          title="Forçar nova geração via Claude"
        >
          <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
          Atualizar
        </button>
      </div>

      {loading && !data ? (
        <div className="text-xs text-muted-foreground py-6 text-center">Consultando a IA…</div>
      ) : !data || data.insights.length === 0 ? (
        <div className="text-xs text-muted-foreground py-6 text-center">
          Nenhum insight disponível. Faça uma conciliação para gerar análises.
        </div>
      ) : (
        <div className="space-y-3">
          {data.insights.map((ins, idx) => (
            <InsightCard key={idx} insight={ins} />
          ))}
        </div>
      )}
    </div>
  );
}

function InsightCard({ insight }: { insight: AiInsight }) {
  const meta = TIPO_ICONE[insight.tipo];
  const Icon = meta.Icon;

  return (
    <div className={cn("flex items-start gap-3 rounded-xl p-3", meta.bg)}>
      <div className={cn("rounded-md p-1.5 shrink-0", meta.cor)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold leading-tight">{insight.titulo}</p>
        <p className="text-xs text-muted-foreground mt-1 leading-snug">{insight.texto}</p>
        {insight.cta && (
          <button className={cn("mt-2 text-xs font-semibold hover:underline", meta.cor)}>
            {insight.cta} →
          </button>
        )}
      </div>
    </div>
  );
}
