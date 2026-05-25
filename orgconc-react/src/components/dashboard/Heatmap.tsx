import { useMemo } from "react";
import type { HeatmapDay } from "@/lib/api";
import { CalendarDays } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  data: HeatmapDay[];
  /** Quantos dias mostrar. Default: 120 (~4 meses, cabe legível em mobile e desktop). */
  dias?: number;
}

const INTENSIDADE_CLASSES = [
  "bg-muted/40",                                // 0 — sem atividade
  "bg-primary/15",                              // 1
  "bg-primary/35",                              // 2
  "bg-primary/55",                              // 3
  "bg-primary/75",                              // 4
  "bg-primary",                                 // 5+
];

export function Heatmap({ data, dias = 120 }: Props) {
  const { semanas, max } = useMemo(() => construirMatriz(data, dias), [data, dias]);

  return (
    <div className="rounded-3xl border glass p-6">
      <div className="flex items-center gap-2 mb-5">
        <CalendarDays className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Volume diário</h3>
        <span className="ml-auto text-[11px] font-mono text-muted-foreground">
          {dias} dias · pico {max}
        </span>
      </div>

      <div className="overflow-x-auto">
        <div
          className="grid gap-[3px]"
          style={{
            gridTemplateRows: "repeat(7, minmax(0, 1fr))",
            gridAutoColumns: "12px",
            gridAutoFlow: "column",
            width: "max-content",
          }}
        >
          {semanas.flat().map((cel, idx) => (
            <div
              key={idx}
              title={cel ? `${cel.data}: ${cel.valor} transações` : ""}
              className={cn(
                "h-3 w-3 rounded-sm transition-colors",
                cel ? INTENSIDADE_CLASSES[intensidade(cel.valor, max)] : "bg-transparent"
              )}
            />
          ))}
        </div>
      </div>

      <Legenda />
    </div>
  );
}

function Legenda() {
  return (
    <div className="mt-4 flex items-center gap-2 text-[10px] text-muted-foreground font-mono uppercase tracking-wider">
      <span>Menos</span>
      {INTENSIDADE_CLASSES.map((cls, i) => (
        <div key={i} className={cn("h-2.5 w-2.5 rounded-sm", cls)} />
      ))}
      <span>Mais</span>
    </div>
  );
}

function intensidade(valor: number, max: number): number {
  if (valor <= 0 || max <= 0) return 0;
  const pct = valor / max;
  if (pct < 0.10) return 1;
  if (pct < 0.30) return 2;
  if (pct < 0.55) return 3;
  if (pct < 0.80) return 4;
  return 5;
}

interface Celula { data: string; valor: number }

function construirMatriz(
  data: HeatmapDay[],
  dias: number,
): { semanas: (Celula | null)[][]; max: number } {
  // Mapa data → valor
  const mapa = new Map<string, number>();
  let max = 0;
  for (const d of data) {
    mapa.set(d.data, d.valor);
    if (d.valor > max) max = d.valor;
  }

  // Calcula o range [hoje - dias, hoje]
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const inicio = new Date(hoje);
  inicio.setDate(inicio.getDate() - (dias - 1));

  // Preenche por semana — primeira coluna pode ter padding nulo para alinhar weekday
  const semanas: (Celula | null)[][] = [];
  let semanaAtual: (Celula | null)[] = new Array(inicio.getDay()).fill(null);

  for (let i = 0; i < dias; i++) {
    const d = new Date(inicio);
    d.setDate(d.getDate() + i);
    const iso = d.toISOString().slice(0, 10);
    const valor = mapa.get(iso) ?? 0;
    semanaAtual.push({ data: iso, valor });
    if (semanaAtual.length === 7) {
      semanas.push(semanaAtual);
      semanaAtual = [];
    }
  }
  if (semanaAtual.length) {
    while (semanaAtual.length < 7) semanaAtual.push(null);
    semanas.push(semanaAtual);
  }

  return { semanas, max };
}
