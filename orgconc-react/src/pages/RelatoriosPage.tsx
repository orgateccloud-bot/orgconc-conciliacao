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
import { carregarHistoricoLocal, listarConciliacoes, type ConciliacaoMeta } from "@/lib/api";
import { HeroCard } from "@/components/HeroCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Download,
  FileText,
  Search,
  TrendingUp,
  AlertTriangle,
  Hash,
  Activity,
  Copy,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { MODO_CX, MODO_LABEL } from "@/lib/constants";
import { toast } from "sonner";

export function RelatoriosPage() {
  const [dbRows, setDbRows] = useState<ConciliacaoMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const local = useMemo(() => carregarHistoricoLocal(), []);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    listarConciliacoes()
      .then(setDbRows)
      .catch(() => setDbRows([]))
      .finally(() => setLoading(false));
  }, []);

  type Row = ConciliacaoMeta & { report_id: string };

  const allRows: Row[] = useMemo(() => {
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
    ) as Row[];
  }, [dbRows, local]);

  const rowsFiltradas = useMemo(() => {
    return allRows.filter((r) => {
      if (busca) {
        const q = busca.toLowerCase();
        if (!r.report_id.toLowerCase().includes(q) && !r.modo.toLowerCase().includes(q)) {
          return false;
        }
      }
      if (dataInicio && new Date(r.criado_em) < new Date(dataInicio)) return false;
      if (dataFim && new Date(r.criado_em) > new Date(dataFim + "T23:59:59")) return false;
      return true;
    });
  }, [allRows, busca, dataInicio, dataFim]);

  // KPIs
  const totalTx = allRows.reduce((s, r) => s + r.total_transacoes, 0);
  const totalAnom = allRows.reduce((s, r) => s + r.total_anomalias, 0);
  const taxaAnom = totalTx > 0 ? ((totalAnom / totalTx) * 100).toFixed(1) : "0";

  // Charts
  const modoData = useMemo(() => {
    const byModo: Record<string, number> = {};
    allRows.forEach((r) => { byModo[r.modo] = (byModo[r.modo] || 0) + 1; });
    return Object.entries(byModo).map(([modo, qtd]) => ({
      modo: MODO_LABEL[modo] ?? modo,
      qtd,
    }));
  }, [allRows]);

  const trendData = useMemo(() => {
    const sorted = [...allRows].sort((a, b) => {
      const ta = a.criado_em ? +new Date(a.criado_em) : 0;
      const tb = b.criado_em ? +new Date(b.criado_em) : 0;
      return ta - tb;
    });
    return sorted.slice(-10).map((r) => ({
      data: new Date(r.criado_em).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }),
      anomalias: r.total_anomalias,
    }));
  }, [allRows]);

  // MELHORIA 5: função para copiar report ID
  function copiarReportId(reportId: string) {
    navigator.clipboard.writeText(reportId).then(() => {
      toast.success("ID copiado!");
    }).catch(() => {
      toast.error("Falha ao copiar ID");
    });
  }

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="03 · RELATÓRIOS"
        title="Histórico de"
        titleAccent="cartas."
        subtitle="Conciliações no banco (quando online) ou histórico local do navegador."
      />

      {/* KPI Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Conciliações",    value: allRows.length,             icon: Hash,          color: "text-primary bg-primary/10" },
          { label: "Transações",      value: totalTx.toLocaleString("pt-BR"), icon: TrendingUp,  color: "text-blue-500 bg-blue-50 dark:bg-blue-950/30" },
          { label: "Anomalias",       value: totalAnom.toLocaleString("pt-BR"), icon: AlertTriangle, color: "text-orange-500 bg-orange-50 dark:bg-orange-950/30" },
          { label: "Taxa anomalias",  value: `${taxaAnom}%`,             icon: Activity,      color: "text-purple-500 bg-purple-50 dark:bg-purple-950/30" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-2xl border glass p-5 flex items-start gap-4">
            <div className={cn("rounded-xl p-2.5", color)}>
              <Icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[11px] text-muted-foreground font-mono uppercase tracking-wide">{label}</p>
              <p className="text-2xl font-bold mt-0.5">{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      {allRows.length > 1 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-3xl border glass p-6">
            <h3 className="text-sm font-semibold mb-4">Anomalias por período</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="data" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="anomalias"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="rounded-3xl border glass p-6">
            <h3 className="text-sm font-semibold mb-4">Por modo de análise</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={modoData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="modo" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="qtd" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="rounded-3xl border overflow-hidden">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 p-4 border-b bg-muted/30">
          <div className="flex items-center gap-2 flex-1 min-w-40">
            <Search className="h-4 w-4 text-muted-foreground shrink-0" />
            <Input
              placeholder="Buscar por ID ou modo…"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              className="h-8 border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 p-0"
            />
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="date"
              value={dataInicio}
              onChange={(e) => setDataInicio(e.target.value)}
              className="rounded-md border px-2 py-1 text-xs bg-background"
            />
            <span>até</span>
            <input
              type="date"
              value={dataFim}
              onChange={(e) => setDataFim(e.target.value)}
              className="rounded-md border px-2 py-1 text-xs bg-background"
            />
          </div>
          <span className="text-xs text-muted-foreground shrink-0">
            {rowsFiltradas.length} resultado(s)
          </span>
        </div>

        {loading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
            ))}
          </div>
        ) : rowsFiltradas.length === 0 ? (
          <div className="p-12 flex flex-col items-center gap-4 text-center">
            <FileText className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              {allRows.length === 0
                ? "Nenhuma conciliação realizada ainda."
                : "Nenhum resultado para este filtro."}
            </p>
            {allRows.length === 0 && (
              <Button size="sm" onClick={() => navigate("/conciliacao")}>
                Fazer primeira conciliação →
              </Button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left p-3 font-semibold">Report ID</th>
                  <th className="text-left p-3 font-semibold">Modo</th>
                  <th className="text-right p-3 font-semibold">Tx</th>
                  <th className="text-right p-3 font-semibold">Anom.</th>
                  <th className="text-left p-3 font-semibold">Data</th>
                  <th className="p-3 font-semibold text-center">Exports</th>
                </tr>
              </thead>
              <tbody>
                {rowsFiltradas.map((r) => (
                  <tr key={r.report_id} className="border-t hover:bg-muted/20">
                    {/* MELHORIA 5: 12 chars + botão copy */}
                    <td className="p-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-xs" title={r.report_id}>
                          {r.report_id.slice(0, 12)}…
                        </span>
                        <button
                          onClick={() => copiarReportId(r.report_id)}
                          className="rounded p-0.5 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                          aria-label="Copiar Report ID"
                          title="Copiar ID completo"
                        >
                          <Copy className="h-3 w-3" />
                        </button>
                      </div>
                    </td>
                    <td className="p-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold",
                          MODO_CX[r.modo] ?? "bg-gray-100 text-gray-700 border-gray-200"
                        )}
                      >
                        {MODO_LABEL[r.modo] ?? r.modo}
                      </span>
                    </td>
                    <td className="p-3 text-right">{r.total_transacoes}</td>
                    <td className="p-3 text-right">
                      <span className={r.total_anomalias > 0 ? "text-orange-500 font-semibold" : ""}>
                        {r.total_anomalias}
                      </span>
                    </td>
                    <td className="p-3 text-xs text-muted-foreground whitespace-nowrap">
                      {new Date(r.criado_em).toLocaleString("pt-BR")}
                    </td>
                    <td className="p-3">
                      <div className="flex items-center justify-center gap-1">
                        {/* MELHORIA 4: target="_blank" em todos os links de download */}
                        {[
                          { label: "HTML", path: r.exports.html },
                          { label: "XLS",  path: r.exports.xlsx },
                          { label: "PDF",  path: r.exports.pdf },
                        ].map(({ label, path }) => (
                          <a
                            key={label}
                            href={path}
                            title={label}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold font-mono border hover:bg-muted transition-colors text-primary"
                          >
                            <Download className="h-2.5 w-2.5" />
                            {label}
                          </a>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
