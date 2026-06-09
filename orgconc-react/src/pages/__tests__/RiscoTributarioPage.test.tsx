import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RiscoTributarioPage } from "@/pages/RiscoTributarioPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    fiscalRiscoTributario: vi.fn(),
  };
});

// sonner é só feedback visual; mockamos as funções usadas pela página.
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

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
          {/* placeholder vazio quando value === "" (permite "desselecionar") */}
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
import { toast } from "sonner";

const CLIENTE = {
  id: "c1",
  nome: "Acme Ltda",
  cnpj: "11222333000181",
  plano: "pro",
  ativo: true,
} as api.Cliente;

const RISCO: api.FiscalRiscoResponse = {
  cliente_id: "c1",
  risco_total_anual: 123456.78,
  risco_despesa_indedutivel_anual: 80000,
  risco_retencoes_anual: 43456.78,
  por_classe_risco: {
    CRITICO: 60000,
    ALTO: 40000,
    MEDIO: 20000,
    BAIXO: 3456.78,
  },
  por_flag: { SEM_NF: 3 },
  contagem_fornecedores: {
    CRITICO: 2,
    ALTO: 3,
    MEDIO: 1,
    BAIXO: 4,
  },
  total_fornecedores: 10,
  top_10_fornecedores: [
    {
      cnpj: "99888777000166",
      razao_social: "Fornecedor Beta",
      risco_anual: 60000,
      classe: "CRITICO",
      flags: ["SEM_NF", "DIVERGENCIA"],
    },
    {
      cnpj: "55444333000122",
      razao_social: "",
      risco_anual: 40000,
      classe: "ALTO",
      flags: [],
    },
  ],
  retencoes: {
    base_pj_anual: 700000,
    retencao_pj_anual: 43456.78,
    total_anual: 43456.78,
    aliquotas: { pis: 0.0065 },
  },
  regime_pressuposto: "Lucro Real",
  aliquota_aplicada_pct: 34,
};

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

  it("mantem app estavel e mostra toast quando listagem de clientes falha", async () => {
    vi.mocked(api.listarClientes).mockRejectedValueOnce(new Error("DB off"));
    render(<RiscoTributarioPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());
    expect(screen.getByText(/Lucro Real/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Falha ao carregar clientes"),
    );
  });

  it("popula o seletor com os clientes carregados", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    render(<RiscoTributarioPage />);
    await waitFor(() =>
      expect(screen.getByRole("option", { name: "Acme Ltda" })).toBeInTheDocument(),
    );
    expect(api.fiscalRiscoTributario).not.toHaveBeenCalled();
  });

  it("ao selecionar cliente, busca risco e renderiza os cards de totais", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValue(RISCO);

    render(<RiscoTributarioPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });

    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    await waitFor(() =>
      expect(api.fiscalRiscoTributario).toHaveBeenCalledWith("c1"),
    );

    // Cards de totais (formatBRL pt-BR)
    await waitFor(() =>
      expect(screen.getByText("Risco Total Anual")).toBeInTheDocument(),
    );
    expect(screen.getByText("R$ 123.456,78")).toBeInTheDocument();
    expect(screen.getByText("R$ 80.000,00")).toBeInTheDocument();
    // regime + alíquota no rodapé do card
    expect(screen.getByText(/Lucro Real · 34% IRPJ\+CSLL/)).toBeInTheDocument();
    expect(screen.getByText("Despesa Indedutível")).toBeInTheDocument();
    expect(screen.getByText("Retenções Não Recolhidas")).toBeInTheDocument();
  });

  it("renderiza a distribuicao por classe com contagens e progressbars", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValue(RISCO);

    render(<RiscoTributarioPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    await screen.findByText("Distribuição por Classe de Risco");

    // contagens de fornecedores por classe (aparecem em label e badge da tabela)
    expect(screen.getAllByText(/\(2 fornec\.\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/\(4 fornec\.\)/).length).toBeGreaterThan(0);

    // uma barra de progresso por classe (4 classes fixas)
    const bars = screen.getAllByRole("progressbar");
    expect(bars.length).toBe(4);
    // CRITICO = 60000 / 123456.78 ≈ 48.6%
    const critico = bars.find((b) =>
      (b.getAttribute("aria-label") ?? "").startsWith("CRITICO:"),
    );
    expect(critico).toBeDefined();
    expect(critico?.getAttribute("aria-label")).toMatch(/CRITICO: 48\.6%/);
  });

  it("renderiza a tabela Top 10 com fallback de razao social e flags", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValue(RISCO);

    render(<RiscoTributarioPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    await screen.findByText("Top 10 Fornecedores por Risco");

    // fornecedor com razão social
    expect(screen.getByText("Fornecedor Beta")).toBeInTheDocument();
    expect(screen.getByText("99888777000166")).toBeInTheDocument();
    // CNPJ do fornecedor sem razão social (cai no fallback "—")
    expect(screen.getByText("55444333000122")).toBeInTheDocument();
    // flags juntadas por ", "
    expect(screen.getByText("SEM_NF, DIVERGENCIA")).toBeInTheDocument();
    // duas linhas -> dois fallbacks "—" (razão social vazia + flags vazias)
    expect(screen.getAllByText("—").length).toBe(2);
  });

  it("nao renderiza a tabela Top 10 quando a lista vem vazia", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValue({
      ...RISCO,
      top_10_fornecedores: [],
    });

    render(<RiscoTributarioPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    // os cards (que dependem de risco) aparecem...
    await screen.findByText("Distribuição por Classe de Risco");
    // ...mas a seção Top 10 não
    expect(
      screen.queryByText("Top 10 Fornecedores por Risco"),
    ).not.toBeInTheDocument();
  });

  it("simulador calcula economia estimada a 34% do valor informado", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValue(RISCO);

    render(<RiscoTributarioPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    await screen.findByText("Simulador de Economia");

    // valor inicial 0 -> economia R$ 0,00
    expect(screen.getByText("R$ 0,00")).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Ex: 1000000");
    await userEvent.type(input, "1000000");

    // 1.000.000 × 0,34 = 340.000
    await waitFor(() =>
      expect(screen.getByText("R$ 340.000,00")).toBeInTheDocument(),
    );
  });

  it("valor nao numerico no simulador zera a economia (fallback || 0)", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValue(RISCO);

    render(<RiscoTributarioPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    await screen.findByText("Simulador de Economia");
    const input = screen.getByPlaceholderText("Ex: 1000000") as HTMLInputElement;

    // digita e limpa -> Number("") === NaN -> || 0
    await userEvent.type(input, "500");
    await userEvent.clear(input);

    await waitFor(() => expect(screen.getByText("R$ 0,00")).toBeInTheDocument());
  });

  it("mostra toast com a mensagem do erro quando fiscalRiscoTributario rejeita (Error)", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalRiscoTributario).mockRejectedValue(new Error("Erro do servidor"));

    render(<RiscoTributarioPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Erro do servidor"),
    );
    // sem risco renderizado, o cabeçalho permanece
    expect(screen.queryByText("Risco Total Anual")).not.toBeInTheDocument();
    expect(screen.getByText(/Lucro Real/i)).toBeInTheDocument();
  });

  it("usa mensagem generica quando o erro nao e instancia de Error", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalRiscoTributario).mockRejectedValue("falha crua");

    render(<RiscoTributarioPage />);
    await screen.findByRole("option", { name: "Acme Ltda" });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Falha ao carregar risco"),
    );
  });
});
