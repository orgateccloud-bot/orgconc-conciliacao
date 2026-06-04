import { describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { auditarA11y, semViolacoesCriticas } from "@/test/axe-helper";
import { ErrorBoundary } from "@/components/ErrorBoundary";

describe("Acessibilidade WCAG 2.1 AA", () => {
  it("ErrorBoundary fallback nao tem violacoes criticas", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    function Bomba(): ReactElement {
      throw new Error("teste");
    }

    const { container } = render(
      <ErrorBoundary>
        <Bomba />
      </ErrorBoundary>,
    );
    const results = await auditarA11y(container);
    expect(semViolacoesCriticas(results)).toBe(true);
  });

  it("formulario simples com label/input passa axe", async () => {
    const { container } = render(
      <form>
        <label htmlFor="email">E-mail</label>
        <input id="email" name="email" type="email" autoComplete="email" />
        <button type="submit" aria-label="Enviar formulario">Enviar</button>
      </form>,
    );
    const results = await auditarA11y(container);
    expect(semViolacoesCriticas(results)).toBe(true);
  });

  it("botao-icone sem aria-label produz violacao critica", async () => {
    const { container } = render(
      <button>
        <svg aria-hidden width="16" height="16">
          <circle cx="8" cy="8" r="6" />
        </svg>
      </button>,
    );
    const results = await auditarA11y(container);
    expect(semViolacoesCriticas(results)).toBe(false);
  });
});
