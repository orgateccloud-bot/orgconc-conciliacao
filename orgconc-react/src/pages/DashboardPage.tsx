import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchActivityFeed,
  fetchAiInsights,
  fetchAuditTimeline,
  fetchDashboardBundle,
  fetchTrustScore,
  type ActivityFeedItem,
  type AiInsightsResponse,
  type AuditTimelineResponse,
  type DashboardBundle,
  type TrustScore,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  AlertTriangle,
  Download,
  FileText,
  LineChart as LineChartIcon,
  Plus,
  RefreshCw,
  TrendingUp,
  Upload,
} from "lucide-react";

import { AIInsightsPanel } from "@/components/dashboard/AIInsightsPanel";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { AuditTimeline } from "@/components/dashboard/AuditTimeline";
import { ComplianceBadges } from "@/components/dashboard/ComplianceBadges";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { DistribuicaoChart } from "@/components/dashboard/DistribuicaoChart";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { SecurityRing } from "@/components/dashboard/SecurityRing";
import { TrendChart } from "@/components/dashboard/TrendChart";

const PERIODO_DIAS = 30;

function fmtNumero(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toLocaleString("pt-BR");
}

function fmtMoeda(n: number): string {
  if (n === 0) return "R$ 0";
  if (Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `R$ ${(n / 1_000).toFixed(1)}k`;
  return `R$ ${n.toFixed(0)}`;
}

export function DashboardPage() {
  const navigate = useNavigate();

  const [bundle, setBundle] = useState<DashboardBundle | null>(null);
  const [trust, setTrust] = useState<TrustScore | null>(null);
  const [insights, setInsights] = useState<AiInsightsResponse | null>(null);
  const [activity, setActivity] = useState<ActivityFeedItem[]>([]);
  const [auditTimeline, setAuditTimeline] = useState<AuditTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [erro, setErro] = useState(false);

  const carregarTudo = useCallback(async () => {
    setLoading(true);
    setErro(false);
    setBundle(null); // limpa stale: garante skeleton no retry e ErroCard se falhar de novo
    const [bundleRes, trustRes, insightsRes, activityRes, auditRes] = await Promise.allSettled([
      fetchDashboardBundle(PERIODO_DIAS),
      fetchTrustScore(PERIODO_DIAS),
      fetchAiInsights(PERIODO_DIAS),
      fetchActivityFeed(10),
      fetchAuditTimeline(10),
    ]);
    if (bundleRes.status === "fulfilled") setBundle(bundleRes.value);
    else setErro(true);
    if (trustRes.status === "fulfilled") setTrust(trustRes.value);
    if (insightsRes.status === "fulfilled") setInsights(insightsRes.value);
    if (activityRes.status === "fulfilled") setActivity(activityRes.value);
    if (auditRes.status === "fulfilled") setAuditTimeline(auditRes.value);
    setLoading(false);
  }, []);

  useEffect(() => {
    carregarTudo();
  }, [carregarTudo]);

  const refreshInsights = useCallback(async () => {
    setInsightsLoading(true);
    try {
      const res = await fetchAiInsights(PERIODO_DIAS, true);
      setInsights(res);
    } catch {
      /* ignora — UI já mostra estado anterior */
    } finally {
      setInsightsLoading(false);
    }
  }, []);

  if (loading && !bundle) {
    return <DashboardSkeleton />;
  }

  const kpis = bundle?.kpis;
  const trend = bundle?.trend ?? [];
  const distribuicao = bundle?.distribuicao ?? [];
  const heatmap = bundle?.heatmap ?? [];

  // Divulgação progressiva: sem nenhuma conciliação, NÃO mostramos gauge/KPIs/charts
  // (evita "saúde 80 / 100%" fantasma). O herói de importação domina a tela.
  const temDados = !!kpis && kpis.conciliacoes > 0;

  return (
    <div className="animate-fade-in space-y-6">
      {/* Título + ações */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight leading-none">
            Conciliação{" "}
            <em className="font-serif not-italic italic text-primary">Bancária</em>
          </h1>
          <ComplianceBadges />
        </div>
        <div className="flex gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => navigate("/relatorios")}
          >
            <Download className="h-4 w-4" aria-hidden="true" /> Exportar
          </Button>
          <Button size="sm" className="gap-2" onClick={() => navigate("/upload")}>
            <Upload className="h-4 w-4" aria-hidden="true" /> Importar extrato
          </Button>
        </div>
      </div>

      {!bundle && erro ? (
        <DashboardShell
          main={<ErroCard onRetry={carregarTudo} />}
          rightbar={<ActivityFeed data={activity} />}
        />
      ) : !temDados ? (
        <DashboardShell
          main={
            <EmptyHero
              onImport={() => navigate("/upload")}
              onConciliar={() => navigate("/conciliacao")}
            />
          }
          rightbar={<ActivityFeed data={activity} />}
        />
      ) : (
        <DashboardShell
          main={
            <>
              {/* Saúde (Trust Score) + Insights da IA */}
              <div className="grid gap-6 lg:grid-cols-3 items-stretch">
                <div className="lg:col-span-2">
                  <SecurityRing data={trust} loading={loading && !trust} />
                </div>
                <AIInsightsPanel
                  data={insights}
                  loading={insightsLoading}
                  onRefresh={refreshInsights}
                />
              </div>

              {/* KPIs */}
              <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
                <KpiCard
                  label="Volume processado"
                  value={kpis ? fmtMoeda(kpis.volume_total) : "—"}
                  desc={kpis ? `${fmtNumero(kpis.transacoes)} transações` : undefined}
                  delta={kpis?.delta.transacoes_pct ?? null}
                  icon={TrendingUp}
                  accent="primary"
                />
                <KpiCard
                  label="Taxa conciliação"
                  value={
                    kpis && kpis.transacoes > 0
                      ? `${(100 - kpis.taxa_anomalias_pct).toFixed(1)}%`
                      : "—"
                  }
                  desc={kpis && kpis.transacoes > 0 ? "transações sem divergência" : "sem transações ainda"}
                  delta={kpis && kpis.transacoes > 0 ? kpis.delta.conciliacoes_pct : null}
                  icon={LineChartIcon}
                  accent="blue"
                />
                <KpiCard
                  label="Anomalias detectadas"
                  value={kpis ? fmtNumero(kpis.anomalias) : "—"}
                  desc={kpis ? `${kpis.taxa_anomalias_pct.toFixed(1)}% das transações` : undefined}
                  delta={kpis?.delta.anomalias_pct ?? null}
                  icon={AlertTriangle}
                  accent="orange"
                  inverso
                />
                <KpiCard
                  label="Conciliações no período"
                  value={kpis ? fmtNumero(kpis.conciliacoes) : "—"}
                  desc={kpis ? `nos últimos ${kpis.periodo_dias} dias` : undefined}
                  delta={kpis?.delta.conciliacoes_pct ?? null}
                  icon={FileText}
                  accent="green"
                />
              </div>

              {/* Charts: tendência (largo) + distribuição */}
              <div className="grid gap-5 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  <TrendChart data={trend} />
                </div>
                <DistribuicaoChart data={distribuicao} />
              </div>

              {/* Heatmap diário */}
              <Heatmap data={heatmap} />

              {/* Trilha de auditoria */}
              <AuditTimeline data={auditTimeline} />
            </>
          }
          rightbar={<ActivityFeed data={activity} />}
        />
      )}
    </div>
  );
}

function ErroCard({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="rounded-3xl border glass p-8 md:p-12 flex flex-col items-center gap-4 text-center">
      <div className="h-14 w-14 rounded-2xl bg-orange-50 dark:bg-orange-950/40 text-orange-500 dark:text-orange-400 flex items-center justify-center">
        <AlertTriangle className="h-7 w-7" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <p className="font-semibold">Não foi possível carregar o dashboard</p>
        <p className="text-sm text-muted-foreground max-w-sm">
          Falha ao buscar as métricas. Verifique sua conexão e tente novamente.
        </p>
      </div>
      <Button onClick={onRetry} variant="outline" className="gap-2">
        <RefreshCw className="h-4 w-4" aria-hidden="true" /> Tentar novamente
      </Button>
    </div>
  );
}

function EmptyHero({
  onImport,
  onConciliar,
}: {
  onImport: () => void;
  onConciliar: () => void;
}) {
  return (
    <div className="rounded-3xl border glass p-8 md:p-12 relative overflow-hidden">
      <div
        className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-brand-gradient opacity-10 blur-3xl"
        aria-hidden="true"
      />
      <div className="relative max-w-2xl">
        <div className="inline-flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-primary mb-4">
          <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Configuração inicial
        </div>
        <h2 className="text-2xl md:text-3xl font-bold leading-tight mb-3">
          Importe o primeiro extrato para abrir a trilha de auditoria.
        </h2>
        <p className="text-sm text-muted-foreground mb-6 max-w-lg leading-relaxed">
          Ainda não há conciliações nesta conta. Os indicadores de saúde, taxa de
          conciliação e risco aparecem{" "}
          <strong className="text-foreground">somente após o primeiro processamento</strong> —
          nada de números antes de existirem dados que os sustentem.
        </p>
        <div className="flex flex-wrap gap-3 mb-8">
          <Button onClick={onImport} className="gap-2">
            <Upload className="h-4 w-4" aria-hidden="true" /> Importar extrato bancário
          </Button>
          <Button variant="outline" onClick={onConciliar} className="gap-2">
            <Plus className="h-4 w-4" aria-hidden="true" /> Nova conciliação
          </Button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-xl">
          <Step n={1} titulo="Importe" desc="OFX, CSV ou PDF do banco do cliente." />
          <Step n={2} titulo="Concilie" desc="Os matchers cruzam lançamentos e guias." />
          <Step n={3} titulo="Audite" desc="Saúde, anomalias e laudo passam a valer." />
        </div>
      </div>
    </div>
  );
}

function Step({ n, titulo, desc }: { n: number; titulo: string; desc: string }) {
  return (
    <div className="flex gap-3">
      <div className="shrink-0 h-6 w-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold font-mono">
        {n}
      </div>
      <div>
        <p className="text-sm font-semibold leading-tight">{titulo}</p>
        <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{desc}</p>
      </div>
    </div>
  );
}
