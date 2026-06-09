import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { DistribuicaoChart } from "@/components/dashboard/DistribuicaoChart";
import type { DistribuicaoItem } from "@/lib/api";

// recharts depende de medições de layout (ResponsiveContainer) que o jsdom não
// fornece — sem largura/altura reais o gráfico não monta seus filhos. Damos um
// tamanho fixo e determinístico para que o PieChart renderize sem lançar.
// Não testamos internals do recharts; apenas garantimos a montagem.
vi.mock("recharts", async (orig) => {
  const actual = await orig<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 400, height: 200 }}>{children}</div>
    ),
  };
});

// Dados determinísticos no formato real de DistribuicaoItem ({ modo, qtd }).
const DADOS: DistribuicaoItem[] = [
  { modo: "simulacao_local", qtd: 12 },
  { modo: "multi_modelo", qtd: 8 },
  { modo: "claude_llm", qtd: 5 },
];

describe("DistribuicaoChart", () => {
  it("renderiza o título e o cabeçalho do card", () => {
    render(<DistribuicaoChart data={DADOS} />);
    expect(screen.getByText("Distribuição por modo")).toBeInTheDocument();
  });

  it("exibe o total agregado de análises quando há dados", () => {
    render(<DistribuicaoChart data={DADOS} />);
    // total = 12 + 8 + 5 = 25
    expect(screen.getByText("25 análises")).toBeInTheDocument();
    expect(screen.queryByText("sem dados")).not.toBeInTheDocument();
  });

  it("monta o gráfico com dados sem lançar exceção", () => {
    expect(() => render(<DistribuicaoChart data={DADOS} />)).not.toThrow();
    // O título continua visível mesmo com o chart montado.
    expect(screen.getByText("Distribuição por modo")).toBeInTheDocument();
  });

  it("mostra o estado vazio quando não há itens", () => {
    render(<DistribuicaoChart data={[]} />);
    expect(screen.getByText("Sem conciliações no período")).toBeInTheDocument();
    expect(screen.getByText("sem dados")).toBeInTheDocument();
    // Sem dados não deve renderizar o sufixo de contagem.
    expect(screen.queryByText(/análises/)).not.toBeInTheDocument();
  });

  it("expõe o título como cabeçalho acessível (role heading)", () => {
    render(<DistribuicaoChart data={DADOS} />);
    const heading = screen.getByRole("heading", { name: "Distribuição por modo" });
    expect(heading).toBeInTheDocument();
  });
});
