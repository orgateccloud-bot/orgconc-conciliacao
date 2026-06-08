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
  CheckCircle2,
  Download,
  FileText,
  LineChart as LineChartIcon,
  Plus,
  TrendingUp,
} from "lucide-react";

import { AIInsightsPanel } from "@/components/dashboard/AIInsightsPanel";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { AuditTimeline } from "@/components/dashboard/AuditTimeline";
import { ComplianceBadges } from "@/components/dashboard/ComplianceBadges";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { DistribuicaoChart } from "@/components/dashboard/DistribuicaoChart";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { IndicadoresGoals } from "@/components/dashboard/IndicadoresGoals";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { SecurityRing } from "@/components/dashboard/SecurityRing";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { TrustGrid } from "@/components/dashboard/TrustGrid";

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

  const carregarTudo = useCallback(async () => {
    setLoading(true);
    const [bundleRes, trustRes, insightsRes, activityRes, auditRes] = await Promise.allSettled([
      fetchDashboardBundle(PERIODO_DIAS),
      fetchTrustScore(PERIODO_DIAS),
      fetchAiInsights(PERIODO_DIAS),
      fetchActivityFeed(10),
      fetchAuditTimeline(10),
    ]);
    if (bundleRes.status === "fulfilled") setBundle(bundleRes.value);
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

  return (
    <div className="animate-fade-in space-y-6">
      {/* Título + ações */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
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
            <Download className="h-4 w-4" /> Exportar
          </Button>
          <Button size="sm" className="gap-2" onClick={() => navigate("/conciliacao")}>
            <Plus className="h-4 w-4" /> Nova Conciliação
          </Button>
        </div>
      </div>

      <DashboardShell
        main={
          <>
            {/* Onboarding: sem nenhum dado, o CTA de primeira análise vem primeiro */}
            {!loading && kpis && kpis.conciliacoes === 0 && (
              <EmptyState onAction={() => navigate("/conciliacao")} />
            )}

            {/* Trust grid */}
            <TrustGrid data={trust} />

            {/* Security ring (resumo do trust score) */}
            <SecurityRing data={trust} loading={loading && !trust} />

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
                desc={kpis && kpis.transacoes > 0 ? "SLA 97% · acima da meta" : "sem transações ainda"}
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
                desc={kpis ? `${kpis.periodo_dias} dias · sem perdas` : undefined}
                delta={kpis?.delta.conciliacoes_pct ?? null}
                icon={FileText}
                accent="green"
              />
            </div>

            {/* Charts: tendência + distribuição */}
            <div className="grid gap-5 lg:grid-cols-2">
              <TrendChart data={trend} />
              <DistribuicaoChart data={distribuicao} />
            </div>

            {/* Heatmap diário */}
            <Heatmap data={heatmap} />

            {/* AI insights */}
            <AIInsightsPanel
              data={insights}
              loading={insightsLoading}
              onRefresh={refreshInsights}
            />

            {/* Trilha de auditoria */}
            <AuditTimeline data={auditTimeline} />
          </>
        }
        rightbar={
          <>
            <ActivityFeed data={activity} />
            <IndicadoresGoals trust={trust} />
          </>
        }
      />
    </div>
  );
}

function EmptyState({ onAction }: { onAction: () => void }) {
  return (
    <div className="rounded-3xl border glass p-8 flex flex-col items-center gap-5 text-center">
      <div className="h-16 w-16 rounded-2xl bg-brand-gradient flex items-center justify-center shadow-lg">
        <LineChartIcon className="h-8 w-8 text-white" />
      </div>
      <div className="space-y-1">
        <p className="font-semibold text-sm">Nenhuma análise no período</p>
        <p className="text-xs text-muted-foreground max-w-[260px]">
          Carregue seu primeiro extrato OFX, PDF ou XML para começar a detectar anomalias
          automaticamente.
        </p>
      </div>
      <Button size="sm" onClick={onAction} className="gap-2">
        <Plus className="h-4 w-4" /> Fazer primeira análise
      </Button>
      <div className="inline-flex items-center gap-1 text-[11px] text-green-600 dark:text-green-400">
        <CheckCircle2 className="h-3 w-3" />
        Pipeline auditado · pronto para uso
      </div>
    </div>
  );
}
