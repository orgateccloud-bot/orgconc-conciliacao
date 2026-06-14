import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DistribuicaoChart } from "@/components/dashboard/DistribuicaoChart";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { Heatmap } from "@/components/dashboard/Heatmap";
import type { DistribuicaoItem, HeatmapDay, TrendPoint } from "@/lib/api";

// recharts' ResponsiveContainer depende de ResizeObserver, ausente no jsdom.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;

describe("DistribuicaoChart", () => {
  it("mostra estado vazio sem dados ('sem dados' + mensagem)", () => {
    render(<DistribuicaoChart data={[]} />);
    expect(screen.getByText("sem dados")).toBeInTheDocument();
    expect(screen.getByText("Sem conciliações no período")).toBeInTheDocument();
  });

  it("soma o total de análises no cabeçalho quando há dados", () => {
    const data: DistribuicaoItem[] = [
      { modo: "llm", qtd: 5 },
      { modo: "simulacao_local", qtd: 3 },
      { modo: "modo_exotico_desconhecido", qtd: 2 }, // sem rótulo mapeado → usa o modo cru
    ];
    render(<DistribuicaoChart data={data} />);
    expect(screen.getByText("10 análises")).toBeInTheDocument();
    expect(screen.queryByText("Sem conciliações no período")).not.toBeInTheDocument();
  });

  it("renderiza o título da seção", () => {
    render(<DistribuicaoChart data={[{ modo: "multi_modelo", qtd: 1 }]} />);
    expect(screen.getByText("Distribuição por modo")).toBeInTheDocument();
    expect(screen.getByText("1 análises")).toBeInTheDocument();
  });
});

describe("TrendChart", () => {
  it("mostra estado vazio sem dados ('sem dados' + mensagem)", () => {
    render(<TrendChart data={[]} />);
    expect(screen.getByText("sem dados")).toBeInTheDocument();
    expect(screen.getByText("Sem conciliações no período")).toBeInTheDocument();
  });

  it("mostra a contagem de pontos no cabeçalho quando há dados", () => {
    const data: TrendPoint[] = [
      { data: "2026-06-01", conciliacoes: 2, transacoes: 120, anomalias: 3 },
      { data: "2026-06-02", conciliacoes: 1, transacoes: 80, anomalias: 0 },
      { data: "2026-06-03", conciliacoes: 4, transacoes: 200, anomalias: 7 },
    ];
    render(<TrendChart data={data} />);
    expect(screen.getByText("Tendência de processamento")).toBeInTheDocument();
    expect(screen.getByText("3 pontos")).toBeInTheDocument();
    expect(screen.queryByText("Sem conciliações no período")).not.toBeInTheDocument();
  });
});

describe("Heatmap", () => {
  beforeEach(() => {
    // Data fixa para tornar o alinhamento de semana/padding determinístico:
    // 10/06/2026 é uma quarta-feira (hora local).
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 5, 10, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  /** Replica o cálculo de data do componente (meia-noite local → ISO). */
  function isoDiasAtras(n: number): string {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - n);
    return d.toISOString().slice(0, 10);
  }

  it("mostra o range de dias e o pico no cabeçalho", () => {
    const data: HeatmapDay[] = [
      { data: isoDiasAtras(0), valor: 100 },
      { data: isoDiasAtras(1), valor: 40 },
    ];
    render(<Heatmap data={data} dias={14} />);
    expect(screen.getByText("Volume diário")).toBeInTheDocument();
    expect(screen.getByText("14 dias · pico 100")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Volume diário — 14 dias, pico de 100 transações/dia" }),
    ).toBeInTheDocument();
  });

  it("usa 120 dias por padrão e pico 0 sem dados", () => {
    render(<Heatmap data={[]} />);
    expect(screen.getByText("120 dias · pico 0")).toBeInTheDocument();
  });

  it("aplica as classes de intensidade conforme o valor relativo ao pico", () => {
    // max = 100 → faixas: <10% → 1, <30% → 2, <55% → 3, <80% → 4, ≥80% → 5.
    const data: HeatmapDay[] = [
      { data: isoDiasAtras(0), valor: 100 }, // 100% → 5
      { data: isoDiasAtras(1), valor: 70 },  // 70%  → 4
      { data: isoDiasAtras(2), valor: 40 },  // 40%  → 3
      { data: isoDiasAtras(3), valor: 20 },  // 20%  → 2
      { data: isoDiasAtras(4), valor: 5 },   // 5%   → 1
      { data: isoDiasAtras(5), valor: 0 },   // 0    → 0
    ];
    render(<Heatmap data={data} dias={14} />);

    expect(screen.getByTitle(`${isoDiasAtras(0)}: 100 transações`)).toHaveClass("bg-primary");
    expect(screen.getByTitle(`${isoDiasAtras(1)}: 70 transações`)).toHaveClass("bg-primary/75");
    expect(screen.getByTitle(`${isoDiasAtras(2)}: 40 transações`)).toHaveClass("bg-primary/55");
    expect(screen.getByTitle(`${isoDiasAtras(3)}: 20 transações`)).toHaveClass("bg-primary/35");
    expect(screen.getByTitle(`${isoDiasAtras(4)}: 5 transações`)).toHaveClass("bg-primary/15");
    expect(screen.getByTitle(`${isoDiasAtras(5)}: 0 transações`)).toHaveClass("bg-muted/40");
  });

  it("dias sem registro na API aparecem como intensidade zero", () => {
    const data: HeatmapDay[] = [{ data: isoDiasAtras(0), valor: 10 }];
    render(<Heatmap data={data} dias={7} />);
    // Ontem não veio no payload → valor 0, classe de "sem atividade".
    expect(screen.getByTitle(`${isoDiasAtras(1)}: 0 transações`)).toHaveClass("bg-muted/40");
  });

  it("não adiciona padding quando o range fecha exatamente a semana (hoje = sábado)", () => {
    // sáb 13/06/2026 com dias=7 → início no domingo 07/06: 7 células exatas, sem nulos.
    vi.setSystemTime(new Date(2026, 5, 13, 12, 0, 0));
    render(<Heatmap data={[]} dias={7} />);
    const grid = screen.getByRole("img", {
      name: "Volume diário — 7 dias, pico de 0 transações/dia",
    });
    expect(grid.children).toHaveLength(7);
    const transparentes = Array.from(grid.children).filter((c) =>
      c.className.includes("bg-transparent"),
    );
    expect(transparentes).toHaveLength(0);
  });

  it("preenche o grid com células transparentes para alinhar os dias da semana", () => {
    // Com hoje = qua 10/06/2026 e dias=14, o início cai em qui 28/05 (getDay=4):
    // 4 nulos no começo + 14 dias + 3 nulos no fim = 21 células (3 semanas).
    render(<Heatmap data={[]} dias={14} />);
    const grid = screen.getByRole("img", {
      name: "Volume diário — 14 dias, pico de 0 transações/dia",
    });
    expect(grid.children).toHaveLength(21);
    const transparentes = Array.from(grid.children).filter((c) =>
      c.className.includes("bg-transparent"),
    );
    expect(transparentes).toHaveLength(7);
  });
});
