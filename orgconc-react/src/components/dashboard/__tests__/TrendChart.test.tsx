import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { TrendChart } from "@/components/dashboard/TrendChart";
import type { TrendPoint } from "@/lib/api";

// recharts não renderiza seus filhos em jsdom: o ResponsiveContainer mede
// largura/altura via ResizeObserver e, sem layout real, fica com 0×0 e não
// monta o gráfico. Substituímos os componentes por wrappers simples para
// garantir determinismo e poder afirmar que o gráfico monta — sem testar
// internals do recharts (que não são nossos).
vi.mock("recharts", () => {
  const Passthrough = ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  );
  const Noop = () => null;
  return {
    ResponsiveContainer: Passthrough,
    LineChart: Passthrough,
    Line: Noop,
    XAxis: Noop,
    YAxis: Noop,
    CartesianGrid: Noop,
    Tooltip: Noop,
    Legend: Noop,
  };
});

// Pontos determinísticos: datas FIXAS (strings literais), sem Date dinâmico.
const PONTOS: TrendPoint[] = [
  { data: "2026-01-05", conciliacoes: 3, transacoes: 120, anomalias: 2 },
  { data: "2026-01-06", conciliacoes: 4, transacoes: 150, anomalias: 0 },
  { data: "2026-01-07", conciliacoes: 2, transacoes: 90, anomalias: 1 },
];

describe("TrendChart", () => {
  it("renderiza o título do card", () => {
    render(<TrendChart data={PONTOS} />);
    expect(screen.getByText("Tendência de processamento")).toBeInTheDocument();
  });

  it("mostra a contagem de pontos quando há dados", () => {
    render(<TrendChart data={PONTOS} />);
    expect(screen.getByText("3 pontos")).toBeInTheDocument();
    // Não deve cair no estado vazio.
    expect(screen.queryByText("sem dados")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Sem conciliações no período"),
    ).not.toBeInTheDocument();
  });

  it("monta o gráfico com dados sem lançar", () => {
    // Se algo no pipeline de dados quebrar, o render lança e o teste falha.
    expect(() => render(<TrendChart data={PONTOS} />)).not.toThrow();
    expect(screen.getByText("Tendência de processamento")).toBeInTheDocument();
  });

  it("exibe o estado vazio quando data está vazio", () => {
    render(<TrendChart data={[]} />);
    expect(screen.getByText("Sem conciliações no período")).toBeInTheDocument();
    expect(screen.getByText("sem dados")).toBeInTheDocument();
    // Sem dados não deve renderizar contagem de pontos.
    expect(screen.queryByText(/\d+ pontos/)).not.toBeInTheDocument();
  });

  it("expõe o título como heading acessível (role)", () => {
    render(<TrendChart data={PONTOS} />);
    expect(
      screen.getByRole("heading", { name: "Tendência de processamento" }),
    ).toBeInTheDocument();
  });
});
