import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ConciliacaoPage } from "@/pages/ConciliacaoPage";

describe("ConciliacaoPage", () => {
  it("mostra empty state quando nao ha resultado no router state", () => {
    render(
      <MemoryRouter>
        <ConciliacaoPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByText(/nenhuma análise ativa/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ir para upload/i })).toBeInTheDocument();
  });

  it("renderiza o cabecalho de analises", () => {
    render(
      <MemoryRouter>
        <ConciliacaoPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/ANÁLISES/i)).toBeInTheDocument();
  });
});
