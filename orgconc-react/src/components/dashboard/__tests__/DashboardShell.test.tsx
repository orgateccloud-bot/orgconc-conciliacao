import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { DashboardShell } from "@/components/dashboard/DashboardShell";

// DashboardShell é um wrapper de layout puro (sem rede, sem router, sem auth):
// recebe `main` (obrigatório) e `rightbar` (opcional, vira <aside>). Por ser
// só layout, não há recharts a mockar — passamos ReactNode determinístico.
describe("DashboardShell", () => {
  it("renderiza o conteúdo principal", () => {
    render(<DashboardShell main={<h1>Visão Geral</h1>} />);
    expect(
      screen.getByRole("heading", { name: "Visão Geral" }),
    ).toBeInTheDocument();
  });

  it("renderiza o rightbar quando fornecido", () => {
    render(
      <DashboardShell
        main={<p>Conteúdo principal</p>}
        rightbar={<p>Painel lateral</p>}
      />,
    );
    expect(screen.getByText("Conteúdo principal")).toBeInTheDocument();
    expect(screen.getByText("Painel lateral")).toBeInTheDocument();
  });

  it("não renderiza o <aside> quando rightbar é omitido (estado vazio)", () => {
    render(<DashboardShell main={<p>Apenas o main</p>} />);
    // Sem rightbar, o landmark complementar (<aside>) não deve existir.
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(screen.getByText("Apenas o main")).toBeInTheDocument();
  });

  it("não renderiza o <aside> quando rightbar é null", () => {
    render(<DashboardShell main={<p>Main só</p>} rightbar={null} />);
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });

  it("expõe o rightbar como landmark complementar (acessibilidade)", () => {
    render(
      <DashboardShell
        main={<p>Main</p>}
        rightbar={<span>Indicadores 2026-06-09</span>}
      />,
    );
    // <aside> tem role implícito "complementary" — landmark navegável por leitor de tela.
    const aside = screen.getByRole("complementary");
    expect(aside).toBeInTheDocument();
    expect(aside).toHaveTextContent("Indicadores 2026-06-09");
  });

  it("mantém main e rightbar em containers distintos", () => {
    render(
      <DashboardShell
        main={<div data-testid="bloco-main">Bloco main</div>}
        rightbar={<div data-testid="bloco-side">Bloco side</div>}
      />,
    );
    const aside = screen.getByRole("complementary");
    // O bloco do main não vive dentro do <aside> lateral.
    expect(aside).not.toContainElement(screen.getByTestId("bloco-main"));
    expect(aside).toContainElement(screen.getByTestId("bloco-side"));
  });
});
