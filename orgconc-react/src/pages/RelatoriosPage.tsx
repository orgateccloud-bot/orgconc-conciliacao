import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { carregarHistoricoLocal, listarConciliacoes, type ConciliacaoMeta } from "@/lib/api";
import { HeroCard } from "@/components/HeroCard";
import { Download } from "lucide-react";

export function RelatoriosPage() {
  const [dbRows, setDbRows] = useState<ConciliacaoMeta[]>([]);
  const local = useMemo(() => carregarHistoricoLocal(), []);

  useEffect(() => {
    listarConciliacoes()
      .then(setDbRows)
      .catch(() => setDbRows([]));
  }, []);

  const chartData = useMemo(() => {
    const byModo: Record<string, number> = {};
    for (const r of local) {
      const m = r.modo || "outro";
      byModo[m] = (byModo[m] || 0) + 1;
    }
    return Object.entries(byModo).map(([modo, qtd]) => ({ modo, qtd }));
  }, [local]);

  type Row = ConciliacaoMeta & { report_id: string };
  const rows: Row[] = dbRows.length
    ? dbRows
    : local.map((r: { id: string; modo: string; ts: string; total_tx: number; total_anom: number }) => ({
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
      })) as Row[];

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="03 · RELATÓRIOS"
        title="Histórico de"
        titleAccent="cartas."
        subtitle="Conciliações no banco (quando online) ou histórico local do navegador."
      />

      {chartData.length > 0 && (
        <div className="rounded-3xl border bg-card p-6 h-64">
          <h3 className="text-sm font-semibold mb-4">Por modo (local)</h3>
          <ResponsiveContainer width="100%" height="90%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="modo" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="qtd" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="rounded-3xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-3">Report ID</th>
              <th className="text-left p-3">Modo</th>
              <th className="text-right p-3">Tx</th>
              <th className="text-right p-3">Anom.</th>
              <th className="text-left p-3">Data</th>
              <th className="p-3">Export</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.report_id} className="border-t">
                <td className="p-3 font-mono text-xs">{r.report_id}</td>
                <td className="p-3">{r.modo}</td>
                <td className="p-3 text-right">{r.total_transacoes}</td>
                <td className="p-3 text-right">{r.total_anomalias}</td>
                <td className="p-3 text-xs">{new Date(r.criado_em).toLocaleString("pt-BR")}</td>
                <td className="p-3">
                  <a href={r.exports.xlsx} className="inline-flex text-primary">
                    <Download className="h-4 w-4" />
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <p className="p-6 text-sm text-muted-foreground">Nenhum relatório ainda.</p>
        )}
      </div>
    </div>
  );
}
