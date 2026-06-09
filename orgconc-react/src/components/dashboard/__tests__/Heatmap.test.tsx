import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { Heatmap } from "@/components/dashboard/Heatmap";
import type { HeatmapDay } from "@/lib/api";

// Datas FIXAS (strings literais) — deterministico, sem valores dinamicos.
// `max` (o "pico") é derivado do array `data` inteiro, independente do range de
// datas relativo a "hoje", então as asserções sobre o pico são estáveis em
// qualquer data de execução. Não testamos a coloração célula-a-célula (depende
// de `new Date()` interno), apenas que o componente monta e expõe os textos/roles.
const dadosFixos: HeatmapDay[] = [
  { data: "2026-01-05", valor: 3 },
  { data: "2026-01-06", valor: 12 },
  { data: "2026-01-07", valor: 0 },
  { data: "2026-01-08", valor: 7 },
];

describe("Heatmap", () => {
  it("renderiza o título e a legenda do heatmap", () => {
    render(<Heatmap data={dadosFixos} />);
    expect(screen.getByText("Volume diário")).toBeInTheDocument();
    expect(screen.getByText("Menos")).toBeInTheDocument();
    expect(screen.getByText("Mais")).toBeInTheDocument();
  });

  it("expõe a grade com role=img e aria-label descritivo (acessibilidade)", () => {
    render(<Heatmap data={dadosFixos} dias={120} />);
    const grade = screen.getByRole("img", {
      name: "Volume diário — 120 dias, pico de 12 transações/dia",
    });
    expect(grade).toBeInTheDocument();
  });

  it("mostra o resumo de dias e pico calculado a partir dos dados", () => {
    render(<Heatmap data={dadosFixos} dias={90} />);
    // O pico (max) é o maior `valor` do array — 12.
    expect(screen.getByText("90 dias · pico 12")).toBeInTheDocument();
  });

  it("trata o estado vazio sem lançar, exibindo pico 0", () => {
    render(<Heatmap data={[]} />);
    expect(screen.getByText("Volume diário")).toBeInTheDocument();
    expect(screen.getByText("120 dias · pico 0")).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "Volume diário — 120 dias, pico de 0 transações/dia",
      }),
    ).toBeInTheDocument();
  });

  it("respeita a prop `dias` no resumo e no aria-label", () => {
    render(<Heatmap data={dadosFixos} dias={30} />);
    expect(screen.getByText("30 dias · pico 12")).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "Volume diário — 30 dias, pico de 12 transações/dia",
      }),
    ).toBeInTheDocument();
  });
});
