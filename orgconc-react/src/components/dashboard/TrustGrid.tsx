import { ShieldCheck, Activity, BadgeCheck } from "lucide-react";
import type { TrustScore } from "@/lib/api";

interface Props {
  data: TrustScore | null;
}

export function TrustGrid({ data }: Props) {
  const ciclos = data?.metricas.total_conciliacoes ?? 0;
  const taxaDeteccao = data?.metricas.taxa_anomalias_pct ?? 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <TrustCard
        icon={BadgeCheck}
        accent="green"
        title={data ? `${data.breakdown.taxa_sucesso_pct}% de conciliações limpas` : "Métricas em cálculo"}
        meta={data ? `Validado em ${ciclos} ciclo${ciclos === 1 ? "" : "s"}` : "Aguardando dados"}
      />
      <TrustCard
        icon={ShieldCheck}
        accent="blue"
        title="Criptografia AES-256"
        meta="TLS 1.3 · ponta a ponta"
      />
      <TrustCard
        icon={Activity}
        accent="purple"
        title="Trilha de auditoria"
        meta={`${ciclos} eventos · hash chain ativa · ${taxaDeteccao}% taxa detecção`}
      />
    </div>
  );
}

const ACCENT: Record<string, string> = {
  green: "bg-green-100 text-green-600 dark:bg-green-950/40 dark:text-green-400",
  blue: "bg-blue-100 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400",
  purple: "bg-purple-100 text-purple-600 dark:bg-purple-950/40 dark:text-purple-400",
};

function TrustCard({
  icon: Icon,
  title,
  meta,
  accent,
}: {
  icon: typeof ShieldCheck;
  title: string;
  meta: string;
  accent: keyof typeof ACCENT;
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border glass p-4">
      <div className={`rounded-xl p-2.5 shrink-0 ${ACCENT[accent]}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold leading-tight truncate">{title}</p>
        <p className="text-xs text-muted-foreground mt-0.5 truncate">{meta}</p>
      </div>
    </div>
  );
}
