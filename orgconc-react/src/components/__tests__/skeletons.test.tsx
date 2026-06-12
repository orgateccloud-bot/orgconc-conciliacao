import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { auditarA11y, semViolacoesCriticas } from "@/test/axe-helper";
import {
  AppBootSkeleton,
  KpiCardSkeleton,
  KpiGridSkeleton,
  ListItemSkeleton,
  ListSkeleton,
  PageSkeleton,
} from "@/components/skeletons";

describe("KpiCardSkeleton", () => {
  it("expõe role status com rótulo acessível de carregamento", () => {
    render(<KpiCardSkeleton />);
    expect(
      screen.getByRole("status", { name: "Carregando indicador" }),
    ).toBeInTheDocument();
  });
});

describe("KpiGridSkeleton", () => {
  it("renderiza 4 cards por padrão", () => {
    render(<KpiGridSkeleton />);
    expect(
      screen.getAllByRole("status", { name: "Carregando indicador" }),
    ).toHaveLength(4);
  });

  it("respeita a prop items para variar a quantidade de cards", () => {
    render(<KpiGridSkeleton items={2} />);
    expect(
      screen.getAllByRole("status", { name: "Carregando indicador" }),
    ).toHaveLength(2);
  });
});

describe("ListSkeleton", () => {
  it("expõe role status com rótulo de lista e 5 linhas por padrão", () => {
    render(<ListSkeleton />);
    const lista = screen.getByRole("status", { name: "Carregando lista" });
    expect(lista.children).toHaveLength(5);
  });

  it("respeita a prop items para variar a quantidade de linhas", () => {
    render(<ListSkeleton items={3} />);
    const lista = screen.getByRole("status", { name: "Carregando lista" });
    expect(lista.children).toHaveLength(3);
  });
});

describe("ListItemSkeleton", () => {
  it("renderiza a linha avulsa sem quebrar", () => {
    const { container } = render(<ListItemSkeleton />);
    expect(container.firstChild).toBeInTheDocument();
  });
});

describe("PageSkeleton", () => {
  it("anuncia o carregamento da página (status + aria-live polite)", () => {
    render(<PageSkeleton />);
    const status = screen.getByRole("status", { name: "Carregando página" });
    expect(status).toHaveAttribute("aria-live", "polite");
  });

  it("inclui o grid de KPIs dentro do esqueleto de página", () => {
    render(<PageSkeleton />);
    expect(
      screen.getAllByRole("status", { name: "Carregando indicador" }),
    ).toHaveLength(4);
  });
});

describe("AppBootSkeleton", () => {
  it("anuncia a inicialização da aplicação (status + aria-live polite)", () => {
    render(<AppBootSkeleton />);
    const status = screen.getByRole("status", { name: "Inicializando aplicação" });
    expect(status).toHaveAttribute("aria-live", "polite");
  });
});

describe("Acessibilidade dos skeletons", () => {
  it("PageSkeleton não tem violações críticas de a11y", async () => {
    const { container } = render(<PageSkeleton />);
    const results = await auditarA11y(container);
    expect(semViolacoesCriticas(results)).toBe(true);
  });
});
