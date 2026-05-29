import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { DistribuicaoItem } from "@/lib/api";
import { RECHARTS_TOOLTIP_STYLE } from "@/lib/recharts";
import { Sparkles } from "lucide-react";

interface Props {
  data: DistribuicaoItem[];
}

const MODO_LABEL: Record<string, string> = {
  simulacao_local: "Simulação local",
  simulacao_local_csv: "Simulação CSV",
  llm: "Claude (single)",
  claude_llm: "Claude (single)",
  llm_csv: "Claude CSV",
  multi_modelo: "Multi-modelo",
};

const CORES = [
  "hsl(var(--primary))",
  "#7BC8E0",
  "#5BA9D6",
  "#1A3A6B",
  "#f97316",
  "#16a34a",
];

export function DistribuicaoChart({ data }: Props) {
  const itens = data.map((d) => ({
    name: MODO_LABEL[d.modo] ?? d.modo,
    value: d.qtd,
  }));
  const total = itens.reduce((s, i) => s + i.value, 0);

  return (
    <div className="rounded-3xl border glass p-6">
      <div className="flex items-center gap-2 mb-5">
        <Sparkles className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Distribuição por modo</h3>
        <span className="ml-auto text-[11px] font-mono text-muted-foreground">
          {total > 0 ? `${total} análises` : "sem dados"}
        </span>
      </div>
      {itens.length === 0 ? (
        <div className="h-[200px] flex items-center justify-center text-xs text-muted-foreground">
          Sem conciliações no período
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={itens}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={45}
              outerRadius={75}
              paddingAngle={2}
              strokeWidth={2}
              stroke="hsl(var(--card))"
            >
              {itens.map((_, idx) => (
                <Cell key={idx} fill={CORES[idx % CORES.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={RECHARTS_TOOLTIP_STYLE} />
            <Legend
              verticalAlign="bottom"
              height={32}
              wrapperStyle={{ fontSize: 11 }}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
