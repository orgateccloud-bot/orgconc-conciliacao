import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GapsFiscaisPage } from "@/pages/GapsFiscaisPage";

// Mocka SOMENTE as funções de API usadas pela página.
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    fiscalConformidade: vi.fn(),
  };
});

// O Radix Select não abre de forma confiável no jsdom; substituímos por um
// <select> nativo que preserva o contrato value/onValueChange usado pela página.
vi.mock("@/components/ui/select", () => {
  type Opt = { value: string; label: string };
  const collect = (node: React.ReactNode, acc: Opt[]) => {
    React.Children.forEach(node, (child) => {
      if (!React.isValidElement(child)) return;
      const el = child as React.ReactElement<{ value?: string; children?: React.ReactNode }>;
      if (el.props && typeof el.props.value === "string") {
        acc.push({ value: el.props.value, label: String(el.props.children ?? "") });
      } else if (el.props && el.props.children) {
        collect(el.props.children, acc);
      }
    });
  };
  return {
    Select: ({
      value,
      onValueChange,
      children,
    }: {
      value: string;
      onValueChange: (v: string) => void;
      children: React.ReactNode;
    }) => {
      const opts: Opt[] = [];
      collect(children, opts);
      return (
        <select
          data-testid="mock-select"
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
        >
          {/* placeholder vazio quando value === "" */}
          {!opts.some((o) => o.value === value) && <option value="" />}
          {opts.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      );
    },
    SelectTrigger: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    SelectValue: () => null,
    SelectContent: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    SelectItem: ({ value, children }: { value: string; children?: React.ReactNode }) => (
      <option value={value}>{children}</option>
    ),
  };
});

import * as React from "react";
import * as api from "@/lib/api";

const CLIENTE = {
  id: "c1",
  nome: "Acme Ltda",
  cnpj: "11222333000181",
  plano: "pro",
  ativo: true,
} as api.Cliente;

const FORNECEDOR: api.FiscalFornecedor = {
  cnpj: "99888777000166",
  razao_social: "Fornecedor Beta",
  volume_pago: 150000,
  volume_nf: 90000,
  conformidade_pct: 60,
  n_pagamentos: 12,
  n_nfes: 7,
  risco_classe: "ALTO",
  risco_tributario_anual: 25000,
  flags: ["SEM_NF", "DIVERGENCIA"],
  periodo_inicio: "2025-01-01",
  periodo_fim: "2025-12-31",
};

const CONFORMIDADE: api.FiscalConformidadeResponse = {
  cliente_id: "c1",
  total: 1,
  fornecedores: [FORNECEDOR],
};

describe("GapsFiscaisPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("dispara o fetch de clientes ao montar e popula o seletor", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);

    render(<GapsFiscaisPage />);

    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));
    // a opção do cliente carregado aparece no select mockado
    await waitFor(() =>
      expect(screen.getByRole("option", { name: "Acme Ltda" })).toBeInTheDocument(),
    );
    // sem cliente selecionado, fiscalConformidade não é chamado
    expect(api.fiscalConformidade).not.toHaveBeenCalled();
  });

  it("renderiza titulo e filtros base", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([]);

    render(<GapsFiscaisPage />);

    expect(screen.getByText("Gaps fiscais")).toBeInTheDocument();
    expect(screen.getByText("Cliente")).toBeInTheDocument();
    expect(screen.getByText("Classe mínima de risco")).toBeInTheDocument();
    expect(screen.getByText("Buscar (CNPJ/razão)")).toBeInTheDocument();
  });

  it("ao selecionar um cliente, busca conformidade e renderiza a tabela de fornecedores", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValue(CONFORMIDADE);

    render(<GapsFiscaisPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });

    const selects = screen.getAllByTestId("mock-select");
    // primeiro select = Cliente
    await userEvent.selectOptions(selects[0], "c1");

    await waitFor(() =>
      expect(api.fiscalConformidade).toHaveBeenCalledWith("c1", undefined),
    );
    // dados renderizados
    await waitFor(() =>
      expect(screen.getByText("Fornecedor Beta")).toBeInTheDocument(),
    );
    expect(screen.getByText("99888777000166")).toBeInTheDocument();
    expect(screen.getByText("ALTO")).toBeInTheDocument();
    expect(screen.getByText("SEM_NF, DIVERGENCIA")).toBeInTheDocument();
    // conformidade formatada com uma casa decimal
    expect(screen.getByText("60.0%")).toBeInTheDocument();
    // contador de fornecedores exibidos + total
    expect(screen.getByText(/fornecedor\(es\) exibidos/)).toBeInTheDocument();
  });

  it("repassa a classe minima ao trocar o filtro de risco", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValue(CONFORMIDADE);

    render(<GapsFiscaisPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });

    const selects = screen.getAllByTestId("mock-select");
    await userEvent.selectOptions(selects[0], "c1");
    await waitFor(() =>
      expect(api.fiscalConformidade).toHaveBeenCalledWith("c1", undefined),
    );

    // segundo select = Classe mínima de risco
    await userEvent.selectOptions(selects[1], "ALTO");
    await waitFor(() =>
      expect(api.fiscalConformidade).toHaveBeenLastCalledWith("c1", "ALTO"),
    );
  });

  it("aplica a busca por CNPJ/razão e exibe empty state quando nada casa", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValue(CONFORMIDADE);

    render(<GapsFiscaisPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });

    const selects = screen.getAllByTestId("mock-select");
    await userEvent.selectOptions(selects[0], "c1");
    await screen.findByText("Fornecedor Beta");

    const input = screen.getByPlaceholderText("Filtrar...");
    // termo que não casa com nenhum fornecedor -> empty state
    await userEvent.type(input, "inexistente");

    await waitFor(() =>
      expect(
        screen.getByText("Nenhum fornecedor para os filtros atuais."),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText("Fornecedor Beta")).not.toBeInTheDocument();
  });

  it("nao quebra quando fiscalConformidade rejeita (mostra estado vazio sem tabela)", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockRejectedValue(new Error("boom"));

    render(<GapsFiscaisPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });

    const selects = screen.getAllByTestId("mock-select");
    await userEvent.selectOptions(selects[0], "c1");

    await waitFor(() => expect(api.fiscalConformidade).toHaveBeenCalled());
    // sem dados: a tabela não é renderizada e o título permanece
    expect(screen.queryByText("Fornecedor Beta")).not.toBeInTheDocument();
    expect(screen.getByText("Gaps fiscais")).toBeInTheDocument();
  });
});
