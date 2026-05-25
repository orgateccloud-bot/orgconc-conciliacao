import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Cpu } from "lucide-react";
import type { ModeloPerf } from "@/lib/api";

interface Props {
  data: ModeloPerf[];
}

const MODO_LABEL: Record<string, string> = {
  simulacao_local: "Sim. local",
  simulacao_local_csv: "Sim. CSV",
  llm: "Claude",
  claude_llm: "Claude",
  llm_csv: "Claude CSV",
  multi_modelo: "Multi-modelo",
};

const CORES = ["hsl(var(--primary))", "#7BC8E0", "#16a34a", "#f97316", "#a855f7"];

export function PerformanceModelos({ data }: Props) {
  const items = data.map((d) => ({
    nome: MODO_LABEL[d.modo] ?? d.modo,
    qtd: d.qtd,
    latency: d.latency_ms_avg,
  }));

  return (
    <div className="rounded-3xl border glass p-6">
      <div className="flex items-center gap-2 mb-4">
        <Cpu className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Performance por modo</h3>
        <span className="ml-auto text-[11px] font-mono text-muted-foreground">
          {items.length > 0 ? `${items.length} modos ativos` : "sem dados"}
        </span>
      </div>

      {items.length === 0 ? (
        <div className="h-[180px] flex items-center justify-center text-xs text-muted-foreground">
          Sem dados de performance no período
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={items} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
              <YAxis type="category" dataKey="nome" tick={{ fontSize: 10 }} width={90} stroke="hsl(var(--muted-foreground))" />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="qtd" name="Análises" radius={[0, 4, 4, 0]}>
                {items.map((_, idx) => (
                  <Cell key={idx} fill={CORES[idx % CORES.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Pills com latency média quando disponivel */}
          {items.some((i) => i.latency !== null) && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {items
                .filter((i) => i.latency !== null)
                .map((i) => (
                  <span
                    key={i.nome}
                    className="inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-[10px] font-mono text-muted-foreground"
                  >
                    {i.nome}: <span className="font-semibold text-foreground">{i.latency}ms</span>
                  </span>
                ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
