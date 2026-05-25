import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ApiError,
  fetchActivityFeed,
  fetchAiInsights,
  fetchAuditTimeline,
  fetchDashboardBundle,
  fetchPerformanceModelos,
  fetchTransacoesRecentes,
  fetchTrustScore,
  listarClientes,
  type ActivityFeedItem,
  type AiInsightsResponse,
  type AuditTimelineResponse,
  type Cliente,
  type DashboardBundle,
  type ModeloPerf,
  type TransacaoRecente,
  type TrustScore,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Users,
  AlertTriangle,
  TrendingUp,
  Plus,
  LineChart as LineChartIcon,
  DollarSign,
} from "lucide-react";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { RightSidebar } from "@/components/dashboard/RightSidebar";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { DistribuicaoChart } from "@/components/dashboard/DistribuicaoChart";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { TransacoesRecentes } from "@/components/dashboard/TransacoesRecentes";
import { SecurityRing } from "@/components/dashboard/SecurityRing";
import { TrustGrid } from "@/components/dashboard/TrustGrid";
import { ComplianceBadges } from "@/components/dashboard/ComplianceBadges";
import { AuditTimeline } from "@/components/dashboard/AuditTimeline";
import { AIInsightsPanel } from "@/components/dashboard/AIInsightsPanel";
import { PerformanceModelos } from "@/components/dashboard/PerformanceModelos";

const DATA_EXTENSO = new Date().toLocaleDateString("pt-BR", {
  weekday: "long",
  day: "2-digit",
  month: "long",
  year: "numeric",
});

const FORMATADOR_BRL_COMPACTO = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [bundle, setBundle] = useState<DashboardBundle | null>(null);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [transacoes, setTransacoes] = useState<TransacaoRecente[]>([]);
  const [trust, setTrust] = useState<TrustScore | null>(null);
  const [auditTimeline, setAuditTimeline] = useState<AuditTimelineResponse | null>(null);
  const [activity, setActivity] = useState<ActivityFeedItem[]>([]);
  const [modelos, setModelos] = useState<ModeloPerf[]>([]);
  const [insights, setInsights] = useState<AiInsightsResponse | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [backendOffline, setBackendOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    Promise.all([
      fetchDashboardBundle(30).catch((e) => {
        if (e instanceof ApiError && e.status === 503) {
          if (!cancelled) setBackendOffline(true);
          return null;
        }
        if (!cancelled) toast.error("Falha ao carregar métricas", { description: e?.message });
        return null;
      }),
      fetchTransacoesRecentes(8).catch(() => [] as TransacaoRecente[]),
      listarClientes().catch(() => [] as Cliente[]),
      fetchTrustScore(30).catch(() => null),
      fetchAuditTimeline(10).catch(() => null),
      fetchActivityFeed(8).catch(() => [] as ActivityFeedItem[]),
      fetchPerformanceModelos(30).catch(() => [] as ModeloPerf[]),
      fetchAiInsights(30, false).catch(() => null),
    ]).then(([b, tx, cs, ts, at, act, mods, ai]) => {
      if (cancelled) return;
      setBundle(b);
      setTransacoes(tx ?? []);
      setClientes(cs ?? []);
      setTrust(ts);
      setAuditTimeline(at);
      setActivity(act ?? []);
      setModelos(mods ?? []);
      setInsights(ai);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const clientesAtivos = clientes.filter((c) => c.ativo !== false).length;
  const primeiroNome = user?.email?.split("@")[0] ?? user?.sub ?? "usuário";

  async function refreshInsights() {
    setInsightsLoading(true);
    try {
      const novo = await fetchAiInsights(30, true);
      setInsights(novo);
      toast.success("Insights atualizados");
    } catch (e) {
      toast.error("Falha ao gerar insights", { description: e instanceof Error ? e.message : undefined });
    } finally {
      setInsightsLoading(false);
    }
  }

  const valoresKpi = useMemo(() => {
    if (!bundle) return null;
    const k = bundle.kpis;
    return {
      conciliacoes: k.conciliacoes,
      transacoes: k.transacoes,
      anomalias: k.anomalias,
      volume: k.volume_total,
      taxa: k.taxa_anomalias_pct,
      delta: k.delta,
    };
  }, [bundle]);

  const mainContent = loading ? (
    <DashboardSkeleton />
  ) : (
    <div className="space-y-6 animate-fade-in">
      <HeroBanner
        nome={primeiroNome}
        onNova={() => navigate("/conciliacao")}
        onRelatorios={() => navigate("/relatorios")}
      />

      <ComplianceBadges />

      <SecurityRing data={trust} />

      <TrustGrid data={trust} />

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Volume processado"
          value={valoresKpi ? FORMATADOR_BRL_COMPACTO.format(valoresKpi.volume) : "—"}
          desc="últimos 30 dias"
          icon={DollarSign}
          accent="primary"
        />
        <KpiCard
          label="Conciliações"
          value={valoresKpi?.conciliacoes ?? 0}
          desc="análises realizadas"
          delta={valoresKpi?.delta.conciliacoes_pct ?? null}
          icon={LineChartIcon}
          accent="blue"
        />
        <KpiCard
          label="Transações"
          value={valoresKpi ? valoresKpi.transacoes.toLocaleString("pt-BR") : "—"}
          desc="linhas analisadas"
          delta={valoresKpi?.delta.transacoes_pct ?? null}
          icon={TrendingUp}
          accent="green"
        />
        <KpiCard
          label="Anomalias"
          value={valoresKpi?.anomalias ?? 0}
          desc={valoresKpi && valoresKpi.taxa > 0 ? `${valoresKpi.taxa}% das transações` : "detectadas"}
          delta={valoresKpi?.delta.anomalias_pct ?? null}
          icon={AlertTriangle}
          accent="orange"
          inverso
        />
      </div>

      {backendOffline && <BackendOfflineCard clientesAtivos={clientesAtivos} />}

      {!backendOffline && (
        <>
          <div className="grid gap-5 lg:grid-cols-2">
            <TrendChart data={bundle?.trend ?? []} />
            <DistribuicaoChart data={bundle?.distribuicao ?? []} />
          </div>
          <Heatmap data={bundle?.heatmap ?? []} dias={120} />
        </>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <AIInsightsPanel data={insights} loading={insightsLoading} onRefresh={refreshInsights} />
        <PerformanceModelos data={modelos} />
      </div>

      <AuditTimeline data={auditTimeline} />

      <TransacoesRecentes data={transacoes} />
    </div>
  );

  return (
    <DashboardShell
      main={mainContent}
      rightbar={<RightSidebar activity={activity} trust={trust} />}
    />
  );
}

function HeroBanner({
  nome,
  onNova,
  onRelatorios,
}: {
  nome: string;
  onNova: () => void;
  onRelatorios: () => void;
}) {
  return (
    <section className="relative overflow-hidden rounded-3xl bg-brand-gradient p-8 lg:p-10 animate-slide-up">
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full blur-3xl opacity-20"
        style={{ background: "radial-gradient(circle, #7BC8E0 0%, transparent 70%)" }}
      />
      <div
        aria-hidden
        className="absolute bottom-0 left-0 right-0 h-px opacity-30"
        style={{ background: "linear-gradient(90deg, transparent, #7BC8E0, transparent)" }}
      />
      <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-[11px] font-mono uppercase tracking-[0.24em] text-blue-200/80">
            {DATA_EXTENSO}
          </p>
          <h1 className="text-3xl lg:text-4xl font-bold tracking-[-0.035em] text-white leading-none">
            ORGATEC
          </h1>
          <p className="text-sm font-light text-blue-100/70">
            Conciliação Bancária Inteligente · Bem-vindo,{" "}
            <span className="text-blue-100 font-medium capitalize">{nome}</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Button className="bg-white text-primary hover:bg-white/90 gap-2 font-semibold" onClick={onNova}>
            <Plus className="h-4 w-4" />
            Nova análise
          </Button>
          <Button
            variant="outline"
            className="border-white/25 text-white hover:bg-white/10 hover:border-white/40 gap-2"
            onClick={onRelatorios}
          >
            <FileText className="h-4 w-4" />
            Relatórios
          </Button>
        </div>
      </div>
    </section>
  );
}

function BackendOfflineCard({ clientesAtivos }: { clientesAtivos: number }) {
  return (
    <div className="rounded-3xl border glass p-8 text-center space-y-3">
      <div className="mx-auto h-12 w-12 rounded-2xl bg-muted/60 flex items-center justify-center">
        <Users className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="text-sm font-semibold">Métricas indisponíveis</h3>
      <p className="text-xs text-muted-foreground max-w-md mx-auto">
        O banco de dados não está acessível agora. KPIs, charts e heatmap voltam quando a conexão for restabelecida.
        Você ainda tem <strong>{clientesAtivos}</strong> cliente{clientesAtivos === 1 ? "" : "s"} ativo
        {clientesAtivos === 1 ? "" : "s"} na carteira e pode usar o sistema normalmente.
      </p>
    </div>
  );
}
