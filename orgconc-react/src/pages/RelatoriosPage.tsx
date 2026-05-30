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
import { KpiCard, Panel } from "@/components/trust";
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
} from "lucide-react";
import { cn } from "@/lib/utils";

const MODO_CX: Record<string, string> = {
  simulacao_local: "bg-gray-100 text-gray-700 border-gray-200",
  claude_llm:      "bg-blue-100 text-blue-700 border-blue-200",
  multi_modelo:    "bg-purple-100 text-purple-700 border-purple-200",
};

const MODO_LABEL: Record<string, string> = {
  simulacao_local: "Simulação",
  claude_llm:      "Claude LLM",
  multi_modelo:    "Multi-modelo",
};

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
    return allRows.slice(-10).map((r) => ({
      data: new Date(r.criado_em).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }),
      anomalias: r.total_anomalias,
    }));
  }, [allRows]);

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="03 · RELATÓRIOS"
        title="Histórico de"
        titleAccent="cartas."
        subtitle="Conciliações no banco (quando online) ou histórico local do navegador."
      />

      {/* KPI Cards — Trust */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Conciliações" value={allRows.length.toLocaleString("pt-BR")} icon={<Hash className="h-5 w-5" />} />
        <KpiCard label="Transações"   value={totalTx.toLocaleString("pt-BR")}        icon={<TrendingUp className="h-5 w-5" />} />
        <KpiCard
          label="Anomalias"
          value={totalAnom.toLocaleString("pt-BR")}
          icon={<AlertTriangle className="h-5 w-5" />}
          delta={totalAnom > 0 ? { value: `${taxaAnom}%`, direction: "crit" } : undefined}
        />
        <KpiCard label="Taxa anomalias" value={`${taxaAnom}%`} icon={<Activity className="h-5 w-5" />} />
      </div>

      {/* Charts */}
      {allRows.length > 1 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Panel title="Anomalias por período">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="data" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="anomalias"
                  stroke="#0052FF"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </Panel>
          <Panel title="Por modo de análise">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={modoData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="modo" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="qtd" fill="#0052FF" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Panel>
        </div>
      )}

      {/* Table (wrapper sem padding, ja tem header customizado) */}
      <div className="trust-glass rounded-3xl overflow-hidden">
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
                    <td className="p-3 font-mono text-xs" title={r.report_id}>
                      {r.report_id.slice(0, 8)}…
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
                        {[
                          { label: "HTML", path: r.exports.html },
                          { label: "XLS",  path: r.exports.xlsx },
                          { label: "PDF",  path: r.exports.pdf },
                        ].map(({ label, path }) => (
                          <a
                            key={label}
                            href={path}
                            title={label}
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
