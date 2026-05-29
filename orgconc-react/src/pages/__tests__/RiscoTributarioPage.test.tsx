import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { RiscoTributarioPage } from "@/pages/RiscoTributarioPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    fiscalRiscoTributario: vi.fn(),
  };
});

import * as api from "@/lib/api";

describe("RiscoTributarioPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renderiza cabecalho e carrega clientes", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<RiscoTributarioPage />);
    expect(screen.getByText(/Lucro Real/i)).toBeInTheDocument();
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());
  });

  it("nao busca risco enquanto nenhum cliente selecionado", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<RiscoTributarioPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());
    expect(api.fiscalRiscoTributario).not.toHaveBeenCalled();
  });

  it("mantem app estavel quando listagem de clientes falha", async () => {
    vi.mocked(api.listarClientes).mockRejectedValueOnce(new Error("DB off"));
    render(<RiscoTributarioPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());
    expect(screen.getByText(/Lucro Real/i)).toBeInTheDocument();
  });
});
