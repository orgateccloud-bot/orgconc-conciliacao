import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  carregarHistoricoLocal,
  listarClientes,
  listarConciliacoes,
  type Cliente,
  type ConciliacaoMeta,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Users,
  AlertTriangle,
  TrendingUp,
  Plus,
  ArrowRight,
  LineChart as LineChartIcon,
  Download,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ListSkeleton } from "@/components/skeletons";

const MODO_LABEL: Record<string, string> = {
  simulacao_local: "Sim.",
  claude_llm: "Claude",
  multi_modelo: "Multi",
};

const DATA_EXTENSO = new Date().toLocaleDateString("pt-BR", {
  weekday: "long",
  day: "2-digit",
  month: "long",
  year: "numeric",
});

export function DashboardPage() {
  const { user } = useAuth();
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [dbRows, setDbRows] = useState<ConciliacaoMeta[]>([]);
  const [carregando, setCarregando] = useState(true);
  const local = useMemo(() => carregarHistoricoLocal(), []);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.allSettled([
      listarClientes().then(setClientes),
      listarConciliacoes().then(setDbRows),
    ]).finally(() => setCarregando(false));
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

  const totalTx = rows.reduce((s, r) => s + r.total_transacoes, 0);
  const totalAnom = rows.reduce((s, r) => s + r.total_anomalias, 0);
  const clientesAtivos = clientes.filter((c) => c.ativo !== false).length;
  const taxaAnom = totalTx > 0 ? ((totalAnom / totalTx) * 100).toFixed(1) : null;

  const modoData = useMemo(() => {
    const byModo: Record<string, number> = {};
    rows.forEach((r) => { byModo[r.modo] = (byModo[r.modo] || 0) + 1; });
    return Object.entries(byModo).map(([modo, qtd]) => ({
      modo: MODO_LABEL[modo] ?? modo,
      qtd,
    }));
  }, [rows]);

  const trendData = useMemo(() => {
    return rows.slice(-8).map((r) => ({
      data: new Date(r.criado_em).toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
      }),
      anomalias: r.total_anomalias,
      transacoes: r.total_transacoes,
    }));
  }, [rows]);

  const primeiroNome = user?.email?.split("@")[0] ?? user?.sub ?? "usuário";

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── HERO BANNER ──────────────────────────────────────────── */}
      <section className="relative overflow-hidden rounded-3xl bg-brand-gradient p-8 lg:p-12 animate-slide-up">
        {/* Orbs decorativos */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full blur-3xl opacity-20"
          style={{ background: "radial-gradient(circle, #7BC8E0 0%, transparent 70%)" }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -left-12 -bottom-16 h-72 w-72 rounded-full blur-3xl opacity-15"
          style={{ background: "radial-gradient(circle, #5BA9D6 0%, transparent 70%)" }}
        />
        {/* Linha de costa no rodapé do banner */}
        <div
          aria-hidden
          className="absolute bottom-0 left-0 right-0 h-px opacity-30"
          style={{ background: "linear-gradient(90deg, transparent, #7BC8E0, transparent)" }}
        />

        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          {/* Texto */}
          <div className="space-y-3">
            <p className="text-[11px] font-mono uppercase tracking-[0.24em] text-blue-200/80">
              {DATA_EXTENSO}
            </p>
            <div>
              <h1 className="text-4xl lg:text-5xl xl:text-[3.5rem] font-bold tracking-[-0.035em] text-white leading-none">
                ORGATEC
              </h1>
              <p className="mt-1.5 text-base font-light text-blue-100/70">
                Conciliação Bancária Inteligente
              </p>
            </div>
            {user && (
              <p className="text-sm text-blue-200/60 font-light">
                Bem-vindo,{" "}
                <span className="text-blue-100 font-medium capitalize">{primeiroNome}</span>
              </p>
            )}
          </div>

          {/* CTAs */}
          <div className="flex flex-wrap gap-3 shrink-0">
            <Button
              className="bg-white text-primary hover:bg-white/90 gap-2 font-semibold shadow-lg"
              onClick={() => navigate("/conciliacao")}
            >
              <Plus className="h-4 w-4" />
              Nova análise
            </Button>
            <Button
              variant="outline"
              className="border-white/25 text-white hover:bg-white/10 hover:border-white/40 gap-2"
              onClick={() => navigate("/relatorios")}
            >
              <FileText className="h-4 w-4" />
              Relatórios
            </Button>
          </div>
        </div>
      </section>

      {/* ── KPI CARDS ─────────────────────────────────────────────── */}
      <section aria-label="Indicadores principais" className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        {[
          {
            label: "Conciliações",
            value: rows.length,
            desc: "total realizadas",
            icon: LineChartIcon,
            bar: "bg-primary",
            iconCx: "bg-primary/10 text-primary",
          },
          {
            label: "Transações",
            value: totalTx.toLocaleString("pt-BR"),
            desc: "linhas analisadas",
            icon: TrendingUp,
            bar: "bg-blue-400",
            iconCx: "bg-blue-100 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400",
          },
          {
            label: "Anomalias",
            value: totalAnom.toLocaleString("pt-BR"),
            desc: taxaAnom ? `${taxaAnom}% das transações` : "detectadas",
            icon: AlertTriangle,
            bar: "bg-orange-400",
            iconCx: "bg-orange-50 text-orange-500 dark:bg-orange-950/40 dark:text-orange-400",
          },
          {
            label: "Clientes",
            value: clientesAtivos,
            desc: "ativos na carteira",
            icon: Users,
            bar: "bg-green-500",
            iconCx: "bg-green-50 text-green-600 dark:bg-green-950/40 dark:text-green-400",
          },
        ].map(({ label, value, desc, icon: Icon, bar, iconCx }) => (
          <div
            key={label}
            role="region"
            aria-label={`${label}: ${value} ${desc}`}
            className="relative overflow-hidden rounded-2xl border glass p-5 hover:shadow-card-hover transition-all"
          >
            {/* Barra de acento no topo */}
            <div aria-hidden className={cn("absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl", bar)} />
            <div className="flex items-start justify-between mb-3">
              <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
                {label}
              </p>
              <div aria-hidden className={cn("rounded-lg p-1.5", iconCx)}>
                <Icon className="h-3.5 w-3.5" />
              </div>
            </div>
            <p className="text-3xl font-bold font-jakarta tracking-tight leading-none">
              {value}
            </p>
            <p className="mt-1.5 text-xs text-muted-foreground">{desc}</p>
          </div>
        ))}
      </section>

      {/* ── CHARTS (só com dados suficientes) ─────────────────────── */}
      {rows.length > 1 && (
        <section aria-label="Gráficos de desempenho" className="grid gap-5 lg:grid-cols-2">
          <figure
            role="img"
            aria-label={`Tendência de anomalias nas últimas ${trendData.length} análises`}
            className="rounded-3xl border glass p-6 m-0"
          >
            <figcaption className="flex items-center gap-2 mb-5">
              <TrendingUp aria-hidden className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold">Anomalias por período</h3>
              <span className="ml-auto text-[11px] font-mono text-muted-foreground">últimas 8</span>
            </figcaption>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={trendData} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="data" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="anomalias"
                  name="Anomalias"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: "hsl(var(--primary))" }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </figure>

          <figure
            role="img"
            aria-label={`Distribuição por modo de análise — ${modoData.length} categorias`}
            className="rounded-3xl border glass p-6 m-0"
          >
            <figcaption className="flex items-center gap-2 mb-5">
              <Sparkles aria-hidden className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold">Por modo de análise</h3>
            </figcaption>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={modoData} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="modo" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="qtd" name="Análises" fill="hsl(var(--primary))" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </figure>
        </section>
      )}

      {/* ── AÇÕES RÁPIDAS + ATIVIDADE RECENTE ─────────────────────── */}
      <div className="grid gap-5 lg:grid-cols-3">
        {/* Feature cards — ações */}
        <div className="space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-widest text-muted-foreground px-1">
            Ações rápidas
          </h3>
          {[
            {
              route: "/conciliacao",
              icon: LineChartIcon,
              label: "Nova conciliação",
              desc: "OFX · PDF · XML · CSV",
              cx: "bg-primary/10 text-primary",
            },
            {
              route: "/clientes",
              icon: Users,
              label: "Gerenciar clientes",
              desc: "Cadastro e consulta SERPRO",
              cx: "bg-blue-100 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400",
            },
            {
              route: "/relatorios",
              icon: FileText,
              label: "Ver relatórios",
              desc: "HTML · Excel · PDF",
              cx: "bg-green-50 text-green-600 dark:bg-green-950/40 dark:text-green-400",
            },
          ].map(({ route, icon: Icon, label, desc, cx }) => (
            <button
              key={route}
              onClick={() => navigate(route)}
              className="w-full rounded-2xl border glass p-4 text-left flex items-center gap-4 hover:shadow-card-hover hover:border-primary/30 transition-all group"
            >
              <div className={cn("rounded-xl p-2.5 shrink-0", cx)}>
                <Icon className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-sm">{label}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0 transition-transform group-hover:translate-x-0.5" />
            </button>
          ))}
        </div>

        {/* Feed de atividade recente */}
        <div className="lg:col-span-2 rounded-3xl border glass p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
              Atividade recente
            </h3>
            {rows.length > 0 && (
              <button
                onClick={() => navigate("/relatorios")}
                className="text-xs text-primary hover:underline"
              >
                Ver tudo →
              </button>
            )}
          </div>

          {carregando && rows.length === 0 ? (
            <ListSkeleton items={4} />
          ) : rows.length === 0 ? (
            <EmptyState onAction={() => navigate("/conciliacao")} />
          ) : (
            <ul aria-label="Lista de análises recentes" className="space-y-2 list-none p-0 m-0">
              {[...rows].reverse().slice(0, 5).map((r) => (
                <li
                  key={r.report_id}
                  className="flex items-center gap-4 rounded-xl px-4 py-3 hover:bg-muted/20 transition-colors text-sm group"
                >
                  {/* Status dot */}
                  <span
                    aria-hidden
                    className={cn(
                      "h-2 w-2 rounded-full shrink-0",
                      r.total_anomalias > 0 ? "bg-orange-400" : "bg-green-500"
                    )}
                  />
                  <span className="sr-only">
                    {r.total_anomalias > 0 ? "Com anomalias" : "Sem anomalias"}
                  </span>
                  {/* ID */}
                  <span className="font-mono text-xs text-muted-foreground w-20 shrink-0 truncate">
                    {r.report_id.slice(0, 8)}…
                  </span>
                  {/* Modo badge */}
                  <span className="hidden sm:inline text-xs text-muted-foreground flex-1">
                    {MODO_LABEL[r.modo] ?? r.modo}
                  </span>
                  {/* Stats */}
                  <span className="text-xs text-muted-foreground hidden md:block">
                    {r.total_transacoes} tx
                  </span>
                  <span
                    className={cn(
                      "text-xs font-semibold w-16 text-right shrink-0",
                      r.total_anomalias > 0 ? "text-orange-500" : "text-green-500"
                    )}
                  >
                    {r.total_anomalias === 0 ? "Limpa" : `${r.total_anomalias} anom.`}
                  </span>
                  {/* Data */}
                  <span className="text-xs text-muted-foreground whitespace-nowrap hidden sm:block w-20 text-right shrink-0">
                    {new Date(r.criado_em).toLocaleDateString("pt-BR")}
                  </span>
                  {/* Download rápido */}
                  <a
                    href={r.exports.xlsx}
                    aria-label={`Baixar planilha Excel da análise ${r.report_id.slice(0, 8)}`}
                    title="Baixar Excel"
                    className="shrink-0 p-1 rounded text-muted-foreground hover:text-primary opacity-0 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-primary transition-opacity"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Download aria-hidden className="h-3.5 w-3.5" />
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onAction }: { onAction: () => void }) {
  return (
    <div className="flex flex-col items-center gap-5 py-10 text-center">
      {/* Ícone ilustrativo */}
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
