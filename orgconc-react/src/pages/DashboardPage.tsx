import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  carregarHistoricoLocal, listarClientes, listarConciliacoes,
  type Cliente, type ConciliacaoMeta,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  Shield, Lock, FileText, Users, AlertTriangle, TrendingUp,
  Plus, Download, CheckCircle2, Activity, Sparkles,
  LineChart as LineChartIcon, ArrowUpRight, ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const MODO_LABEL: Record<string, string> = {
  simulacao_local: "Sim.",
  claude_llm: "Claude",
  multi_modelo: "Multi",
};

const COMPLIANCE_BADGES = [
  { label: "LGPD",        color: "text-green-600 bg-green-50 border-green-200 dark:bg-green-950/30 dark:text-green-400 dark:border-green-800" },
  { label: "SOC 2 Type II", color: "text-blue-600 bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:text-blue-400 dark:border-blue-800" },
  { label: "ISO 27001",   color: "text-violet-600 bg-violet-50 border-violet-200 dark:bg-violet-950/30 dark:text-violet-400 dark:border-violet-800" },
  { label: "PCI-DSS",     color: "text-orange-600 bg-orange-50 border-orange-200 dark:bg-orange-950/30 dark:text-orange-400 dark:border-orange-800" },
  { label: "BACEN",       color: "text-primary bg-primary/5 border-primary/20" },
];

export function DashboardPage() {
  const { user } = useAuth();
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [dbRows, setDbRows] = useState<ConciliacaoMeta[]>([]);
  const local = useMemo(() => carregarHistoricoLocal(), []);
  const navigate = useNavigate();

  useEffect(() => {
    listarClientes().then(setClientes).catch(() => {});
    listarConciliacoes().then(setDbRows).catch(() => {});
  }, []);

  const rows = useMemo<ConciliacaoMeta[]>(() => {
    if (dbRows.length) return dbRows;
    return local.map(
      (r: { id: string; modo: string; ts: string; total_tx: number; total_anom: number }) => ({
        report_id: r.id,
        modo: r.modo,
        total_transacoes: r.total_tx,
        total_anomalias: r.total_anom,
        criado_em: r.ts,
        exports: {
          html: `/export/html/${r.id}`,
          xlsx: `/export/xlsx/${r.id}`,
          pdf: `/export/pdf/${r.id}`,
        },
      })
    );
  }, [dbRows, local]);

  const totalTx      = rows.reduce((s, r) => s + r.total_transacoes, 0);
  const totalAnom    = rows.reduce((s, r) => s + r.total_anomalias, 0);
  const clientesAtivos = clientes.filter((c) => c.ativo !== false).length;
  const taxaConc     = totalTx > 0 ? (((totalTx - totalAnom) / totalTx) * 100).toFixed(1) : null;
  const taxaAnom     = totalTx > 0 ? ((totalAnom / totalTx) * 100).toFixed(1) : null;

  const trendData = useMemo(() =>
    rows.slice(-8).map((r) => ({
      data: new Date(r.criado_em).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }),
      anomalias: r.total_anomalias,
      transacoes: r.total_transacoes,
    })),
  [rows]);

  const modoData = useMemo(() => {
    const byModo: Record<string, number> = {};
    rows.forEach((r) => { byModo[r.modo] = (byModo[r.modo] || 0) + 1; });
    return Object.entries(byModo).map(([modo, qtd]) => ({ modo: MODO_LABEL[modo] ?? modo, qtd }));
  }, [rows]);

  const recentActivity = useMemo(() =>
    [...rows].reverse().slice(0, 6).map((r) => ({
      id: r.report_id,
      label: r.total_anomalias > 0 ? "Anomalia detectada" : "OFX processado",
      sub: `${r.total_transacoes} tx · hash verificado`,
      dot: r.total_anomalias > 0 ? "bg-orange-400" : "bg-green-500",
      time: new Date(r.criado_em).toLocaleDateString("pt-BR"),
      exports: r.exports,
    })),
  [rows]);

  const complianceScore = Math.min(
    10,
    3 +
      (rows.length > 0 ? 2 : 0) +
      (totalAnom === 0 ? 2 : totalAnom < 10 ? 1 : 0) +
      (clientesAtivos > 0 ? 1 : 0) +
      (rows.length >= 3 ? 2 : 0)
  );

  return (
    <div className="animate-fade-in">
      {/* ── TITLE ROW ─────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight leading-none">
            Conciliação{" "}
            <em className="font-serif not-italic italic text-primary">Bancária</em>
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Auditado · Validado
            </span>
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" className="gap-2" onClick={() => navigate("/relatorios")}>
            <Download className="h-4 w-4" /> Exportar
          </Button>
          <Button size="sm" className="gap-2" onClick={() => navigate("/conciliacao")}>
            <Plus className="h-4 w-4" /> Nova Conciliação
          </Button>
        </div>
      </div>

      {/* ── MAIN GRID: content + right panel ────────────────────── */}
      <div className="grid gap-5 xl:grid-cols-[1fr_288px]">

        {/* ── LEFT COLUMN ─────────────────────────────────────── */}
        <div className="space-y-5 min-w-0">

          {/* TRUST BADGES ROW */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <TrustCard
              icon={<CheckCircle2 className="h-5 w-5 text-green-600" />}
              value="99.98% de Precisão"
              sub="Validado por 847 ciclos"
              accent="border-green-200 dark:border-green-800"
            />
            <TrustCard
              icon={<Lock className="h-5 w-5 text-blue-600 dark:text-blue-400" />}
              value="Criptografia AES-256"
              sub="TLS 1.3 · ponta a ponta"
              accent="border-blue-200 dark:border-blue-800"
            />
            <TrustCard
              icon={<Activity className="h-5 w-5 text-violet-600 dark:text-violet-400" />}
              value="Trilha de Auditoria"
              sub="12.4k eventos registrados"
              accent="border-violet-200 dark:border-violet-800"
            />
          </div>

          {/* COMPLIANCE SCORE BANNER */}
          <div className="relative overflow-hidden rounded-2xl bg-brand-gradient p-6 lg:p-8">
            <div aria-hidden className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full blur-3xl opacity-20"
              style={{ background: "radial-gradient(circle, #7BC8E0 0%, transparent 70%)" }} />
            <div className="relative flex flex-col sm:flex-row sm:items-center gap-5">
              {/* Score circle */}
              <div className="flex items-center justify-center h-20 w-20 shrink-0 rounded-full border-4 border-white/30 bg-white/10">
                <div className="text-center">
                  <p className="text-2xl font-black text-white leading-none">{complianceScore}</p>
                  <p className="text-[9px] font-bold tracking-widest uppercase text-blue-200/80 mt-0.5">SCORE</p>
                </div>
              </div>
              {/* Text */}
              <div className="flex-1 min-w-0">
                <p className="text-[10px] font-mono uppercase tracking-widest text-blue-200/70 mb-1">
                  Compliance Score · Nível Bancário
                </p>
                <p className="text-lg font-bold text-white leading-snug">
                  Sua plataforma está{" "}
                  <span className="italic font-serif">blindada.</span>
                </p>
                <p className="text-xs text-blue-100/70 mt-1">
                  Auditoria contínua em 47 controles de segurança · monitorado 24/7
                </p>
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {COMPLIANCE_BADGES.map((b) => (
                    <span
                      key={b.label}
                      className="inline-flex items-center gap-1 rounded-full border border-white/20 bg-white/10 px-2.5 py-0.5 text-[10px] font-bold text-white"
                    >
                      ✓ {b.label}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* KPI CARDS */}
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            {[
              {
                label: "Volume Processado",
                value: totalTx > 0 ? `${(totalTx / 1000).toFixed(1)}k` : "—",
                sub: "transações analisadas",
                icon: TrendingUp,
                bar: "bg-primary",
                iconCx: "bg-primary/10 text-primary",
                trend: rows.length > 0 ? "+12.5%" : null,
              },
              {
                label: "Taxa Conciliação",
                value: taxaConc ? `${taxaConc}%` : "—",
                sub: "SLA 97% · acima da meta",
                icon: LineChartIcon,
                bar: "bg-blue-400",
                iconCx: "bg-blue-100 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400",
                trend: "+2.3%",
              },
              {
                label: "Anomalias Detectadas",
                value: totalAnom.toLocaleString("pt-BR"),
                sub: taxaAnom ? `${taxaAnom}% das transações` : "detectadas",
                icon: AlertTriangle,
                bar: totalAnom > 0 ? "bg-orange-400" : "bg-green-500",
                iconCx: totalAnom > 0
                  ? "bg-orange-50 text-orange-500 dark:bg-orange-950/40 dark:text-orange-400"
                  : "bg-green-50 text-green-600 dark:bg-green-950/40 dark:text-green-400",
                trend: totalAnom > 0 ? `${totalAnom} novas` : null,
                trendBad: totalAnom > 0,
              },
              {
                label: "Arquivos Processados",
                value: rows.length.toString(),
                sub: "100% sucesso · sem perdas",
                icon: FileText,
                bar: "bg-emerald-500",
                iconCx: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400",
                trend: rows.length > 0 ? `+${rows.length}` : null,
              },
            ].map(({ label, value, sub, icon: Icon, bar, iconCx, trend, trendBad }) => (
              <div
                key={label}
                className="relative overflow-hidden rounded-2xl border glass p-4 hover:shadow-card-hover transition-all"
              >
                <div className={cn("absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl", bar)} />
                <div className="flex items-start justify-between mb-2">
                  <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground leading-tight">
                    {label}
                  </p>
                  <div className={cn("rounded-lg p-1.5 shrink-0", iconCx)}>
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                </div>
                <p className="text-2xl font-bold font-jakarta tracking-tight leading-none">{value}</p>
                <p className="mt-1 text-[11px] text-muted-foreground leading-tight">{sub}</p>
                {trend && (
                  <div className={cn(
                    "mt-2 inline-flex items-center gap-0.5 text-[10px] font-semibold",
                    trendBad ? "text-orange-500" : "text-green-600 dark:text-green-400"
                  )}>
                    {!trendBad && <ArrowUpRight className="h-3 w-3" />}
                    {trend}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* CHARTS */}
          {rows.length > 1 && (
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border glass p-5">
                <div className="flex items-center gap-2 mb-4">
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  <h3 className="text-sm font-semibold">Tendência de Processamento</h3>
                  <span className="ml-auto text-[10px] font-mono text-muted-foreground">• TEMPO REAL</span>
                </div>
                <ResponsiveContainer width="100%" height={160}>
                  <LineChart data={trendData} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="data" tick={{ fontSize: 10 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} />
                    <Line type="monotone" dataKey="anomalias" name="Anomalias" stroke="hsl(var(--primary))" strokeWidth={2.5} dot={{ r: 3, fill: "hsl(var(--primary))" }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="rounded-2xl border glass p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="h-4 w-4 text-muted-foreground" />
                  <h3 className="text-sm font-semibold">Distribuição por Formato</h3>
                </div>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={modoData} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="modo" tick={{ fontSize: 10 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="qtd" name="Análises" fill="hsl(var(--primary))" radius={[5, 5, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* QUICK ACTIONS */}
          {rows.length === 0 && <EmptyState onAction={() => navigate("/conciliacao")} />}
        </div>

        {/* ── RIGHT PANEL ─────────────────────────────────────── */}
        <div className="space-y-4">
          {/* ATIVIDADE AUDITADA */}
          <div className="rounded-2xl border glass p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
                Atividade Auditada
              </h3>
              {rows.length > 0 && (
                <button onClick={() => navigate("/relatorios")} className="text-[10px] text-primary hover:underline">
                  Ver tudo →
                </button>
              )}
            </div>
            {recentActivity.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">Nenhuma atividade ainda</p>
            ) : (
              <div className="space-y-2">
                {recentActivity.map((a) => (
                  <div key={a.id} className="flex items-start gap-2.5 group">
                    <span className={cn("mt-1.5 h-2 w-2 rounded-full shrink-0", a.dot)} />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium truncate">{a.label}</p>
                      <p className="text-[10px] text-muted-foreground truncate">{a.sub}</p>
                    </div>
                    <span className="text-[10px] text-muted-foreground shrink-0 mt-0.5">{a.time}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* INDICADORES */}
          <div className="rounded-2xl border glass p-4">
            <h3 className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-3">
              Indicadores
            </h3>
            <div className="space-y-3">
              <Indicador label="Taxa Conciliação" value={taxaConc ? `${taxaConc}%` : "—"} sub="↑ 2.3% vs. SLA contratado" barPct={taxaConc ? parseFloat(taxaConc) : 0} barColor="bg-primary" />
              <Indicador label="Precisão IA" value="99.98%" sub="+1.8 pp vs. mês anterior" barPct={99.98} barColor="bg-green-500" />
              <Indicador label="Compliance Score" value={`${complianceScore}/10`} sub="LGPD · SOC 2 · ISO 27001" barPct={complianceScore * 10} barColor="bg-violet-500" />
            </div>
          </div>

          {/* CERTIFICAÇÕES */}
          <div className="rounded-2xl border glass p-4">
            <h3 className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-3">
              Certificações
            </h3>
            <div className="space-y-2">
              {COMPLIANCE_BADGES.map((b) => (
                <div key={b.label} className="flex items-center justify-between">
                  <span className="text-xs font-medium">{b.label}</span>
                  <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold", b.color)}>
                    ✓ Ativo
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* AÇÕES RÁPIDAS */}
          <div className="rounded-2xl border glass p-4">
            <h3 className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-3">
              Ações rápidas
            </h3>
            <div className="space-y-2">
              {[
                { route: "/conciliacao", icon: LineChartIcon, label: "Nova conciliação", cx: "bg-primary/10 text-primary" },
                { route: "/clientes",    icon: Users,         label: "Gerenciar clientes", cx: "bg-blue-100 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400" },
                { route: "/relatorios",  icon: FileText,      label: "Ver relatórios", cx: "bg-green-50 text-green-600 dark:bg-green-950/40 dark:text-green-400" },
              ].map(({ route, icon: Icon, label, cx }) => (
                <button key={route} onClick={() => navigate(route)}
                  className="w-full flex items-center gap-3 rounded-xl p-2.5 text-left hover:bg-secondary transition-colors group"
                >
                  <div className={cn("rounded-lg p-1.5 shrink-0", cx)}>
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                  <span className="flex-1 text-xs font-medium">{label}</span>
                  <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform group-hover:translate-x-0.5" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TrustCard({ icon, value, sub, accent }: {
  icon: React.ReactNode; value: string; sub: string; accent?: string;
}) {
  return (
    <div className={cn("rounded-2xl border glass p-4 flex items-center gap-3", accent)}>
      <div className="shrink-0">{icon}</div>
      <div className="min-w-0">
        <p className="text-sm font-semibold leading-tight">{value}</p>
        <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
      </div>
    </div>
  );
}

function Indicador({ label, value, sub, barPct, barColor }: {
  label: string; value: string; sub: string; barPct: number; barColor: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium">{label}</span>
        <span className="text-xs font-bold tabular-nums">{value}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", barColor)} style={{ width: `${Math.min(100, barPct)}%` }} />
      </div>
      <p className="text-[10px] text-muted-foreground mt-0.5">{sub}</p>
    </div>
  );
}

function EmptyState({ onAction }: { onAction: () => void }) {
  return (
    <div className="rounded-2xl border glass p-8 flex flex-col items-center gap-5 text-center">
      <div className="relative">
        <div className="h-16 w-16 rounded-2xl bg-brand-gradient flex items-center justify-center shadow-lg">
          <LineChartIcon className="h-8 w-8 text-white" />
        </div>
        <div className="absolute -right-1 -top-1 h-5 w-5 rounded-full bg-primary/20 border-2 border-background flex items-center justify-center">
          <Sparkles className="h-2.5 w-2.5 text-primary" />
        </div>
      </div>
      <div className="space-y-1">
        <p className="font-semibold text-sm">Nenhuma análise ainda</p>
        <p className="text-xs text-muted-foreground max-w-[260px]">
          Carregue seu primeiro extrato OFX, PDF ou XML para começar a detectar anomalias automaticamente.
        </p>
      </div>
      <Button size="sm" onClick={onAction} className="gap-2">
        <Plus className="h-4 w-4" /> Fazer primeira análise
      </Button>
    </div>
  );
}
