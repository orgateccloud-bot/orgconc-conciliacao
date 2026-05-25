import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrendPoint } from "@/lib/api";
import { TrendingUp } from "lucide-react";

interface Props {
  data: TrendPoint[];
}

export function TrendChart({ data }: Props) {
  const pontos = data.map((p) => ({
    label: new Date(p.data).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }),
    transacoes: p.transacoes,
    anomalias: p.anomalias,
  }));

  return (
    <div className="rounded-3xl border glass p-6">
      <div className="flex items-center gap-2 mb-5">
        <TrendingUp className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Tendência de processamento</h3>
        <span className="ml-auto text-[11px] font-mono text-muted-foreground">
          {pontos.length > 0 ? `${pontos.length} pontos` : "sem dados"}
        </span>
      </div>
      {pontos.length === 0 ? (
        <EmptyChart mensagem="Sem conciliações no período" />
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={pontos} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
            <YAxis allowDecimals={false} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                fontSize: 12,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11, paddingTop: 4 }} />
            <Line
              type="monotone"
              dataKey="transacoes"
              name="Transações"
              stroke="hsl(var(--primary))"
              strokeWidth={2.5}
              dot={{ r: 2.5, fill: "hsl(var(--primary))" }}
              activeDot={{ r: 5 }}
            />
            <Line
              type="monotone"
              dataKey="anomalias"
              name="Anomalias"
              stroke="#f97316"
              strokeWidth={2}
              dot={{ r: 2, fill: "#f97316" }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

function EmptyChart({ mensagem }: { mensagem: string }) {
  return (
    <div className="h-[200px] flex items-center justify-center text-xs text-muted-foreground">
      {mensagem}
    </div>
  );
}
