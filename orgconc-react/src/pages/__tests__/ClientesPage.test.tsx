import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ClientesPage } from "@/pages/ClientesPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    criarCliente: vi.fn(),
    atualizarCliente: vi.fn(),
    listarConciliacoesDoCliente: vi.fn(),
  };
});

import * as api from "@/lib/api";

const CLIENTE = {
  id: "c1",
  nome: "Acme Ltda",
  cnpj: "11222333000181",
  plano: "pro",
  ativo: true,
} as api.Cliente;

describe("ClientesPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("mostra titulo e formulario de novo cliente", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ClientesPage />);
    expect(screen.getByText("Novo cliente")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cadastrar cliente/i })).toBeInTheDocument();
  });

  it("lista clientes retornados pela API", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());
    expect(api.listarClientes).toHaveBeenCalledTimes(1);
  });

  it("mostra empty state quando nao ha clientes", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ClientesPage />);
    await waitFor(() =>
      expect(screen.getByText(/nenhum cliente cadastrado ainda/i)).toBeInTheDocument(),
    );
  });
});
