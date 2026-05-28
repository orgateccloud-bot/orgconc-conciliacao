import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "@/components/ErrorBoundary";

function Bomba({ explode }: { explode: boolean }): JSX.Element {
  if (explode) throw new Error("kaboom");
  return <span>tudo bem</span>;
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // silencia o console.error que o React dispara em erros capturados
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("renderiza children quando nao ha erro", () => {
    render(
      <ErrorBoundary>
        <Bomba explode={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("tudo bem")).toBeInTheDocument();
  });

  it("mostra fallback padrao quando filho lanca", () => {
    render(
      <ErrorBoundary>
        <Bomba explode={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Algo deu errado")).toBeInTheDocument();
    expect(screen.getByText(/kaboom/)).toBeInTheDocument();
  });

  it("oferece botao tentar novamente quando ha erro", () => {
    render(
      <ErrorBoundary>
        <Bomba explode={true} />
      </ErrorBoundary>,
    );
    const botao = screen.getByText("Tentar novamente");
    expect(botao).toBeInTheDocument();
    // O click reseta hasError; o remount com props diferentes eh
    // testado via uso real (RouterProvider troca a tree).
    fireEvent.click(botao);
  });
});
