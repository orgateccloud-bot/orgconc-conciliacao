import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ContratosPage } from "@/pages/ContratosPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    listarContratos: vi.fn(),
    criarContrato: vi.fn(),
  };
});

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

import * as api from "@/lib/api";
import { toast } from "sonner";

const CLIENTE = {
  id: "cli-1",
  nome: "Acme Ltda",
  cnpj: "11222333000181",
  plano: "pro",
  ativo: true,
} as api.Cliente;

const CONTRATO = {
  id: "ct-1",
  cliente_id: "cli-1",
  descricao: "Seguro frota",
  valor: 780,
  periodicidade: "mensal",
  padrao_memo: "SEGURO",
  conta_contabil: "3.1.2.04.005",
  ativo: true,
  criado_em: "2026-01-01T00:00:00Z",
} as api.Contrato;

const CONTRATO_MINIMO = {
  id: "ct-2",
  cliente_id: "cli-orfao-xyz12345",
  descricao: "Leasing veiculo",
  valor: 1200.5,
  periodicidade: null,
  padrao_memo: null,
  conta_contabil: null,
  ativo: true,
  criado_em: "2026-02-01T00:00:00Z",
} as api.Contrato;

describe("ContratosPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("dispara o fetch de clientes e contratos ao montar", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    vi.mocked(api.listarContratos).mockResolvedValueOnce([]);

    render(<ContratosPage />);

    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));
    expect(api.listarContratos).toHaveBeenCalledTimes(1);
  });

  it("mostra titulo e formulario de novo contrato", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    vi.mocked(api.listarContratos).mockResolvedValueOnce([]);

    render(<ContratosPage />);

    expect(screen.getByText("Novo contrato")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /cadastrar contrato/i }),
    ).toBeInTheDocument();
    // aguarda o carregamento inicial concluir para nao vazar estado entre testes
    await waitFor(() => expect(api.listarContratos).toHaveBeenCalled());
  });

  it("renderiza os contratos retornados pela API", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.listarContratos).mockResolvedValueOnce([CONTRATO]);

    render(<ContratosPage />);

    await waitFor(() =>
      expect(screen.getByText("Seguro frota")).toBeInTheDocument(),
    );
    // nome do cliente resolvido pelo mapa id -> nome (renderizado na celula da tabela).
    // "Acme Ltda" tambem aparece no <option> oculto do Radix Select, entao
    // confirmamos via celula <td>.
    const celulaCliente = screen
      .getAllByText("Acme Ltda")
      .find((el) => el.tagName === "TD");
    expect(celulaCliente).toBeInTheDocument();
    // valor formatado em pt-BR
    expect(screen.getByText("780,00")).toBeInTheDocument();
    expect(screen.getByText("SEGURO")).toBeInTheDocument();
    expect(screen.getByText("3.1.2.04.005")).toBeInTheDocument();
  });

  it("usa fallbacks para campos nulos e cliente_id sem nome", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    vi.mocked(api.listarContratos).mockResolvedValueOnce([CONTRATO_MINIMO]);

    render(<ContratosPage />);

    await waitFor(() =>
      expect(screen.getByText("Leasing veiculo")).toBeInTheDocument(),
    );
    // cliente_id encurtado (slice 0,8) quando nao ha nome mapeado
    expect(screen.getByText("cli-orfa")).toBeInTheDocument();
    // periodicidade / padrao_memo / conta_contabil nulos viram "—"
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("mostra empty state quando nao ha contratos", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    vi.mocked(api.listarContratos).mockResolvedValueOnce([]);

    render(<ContratosPage />);

    await waitFor(() =>
      expect(
        screen.getByText(/nenhum contrato cadastrado/i),
      ).toBeInTheDocument(),
    );
  });

  it("filtra os contratos pela busca por descricao", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.listarContratos).mockResolvedValueOnce([
      CONTRATO,
      CONTRATO_MINIMO,
    ]);

    const user = userEvent.setup();
    render(<ContratosPage />);

    await waitFor(() =>
      expect(screen.getByText("Seguro frota")).toBeInTheDocument(),
    );

    const busca = screen.getByPlaceholderText("Buscar por descrição ou valor…");
    await user.type(busca, "leasing");

    await waitFor(() =>
      expect(screen.queryByText("Seguro frota")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Leasing veiculo")).toBeInTheDocument();
  });

  it("nao quebra e avisa via toast quando o fetch falha", async () => {
    vi.mocked(api.listarClientes).mockRejectedValueOnce(new Error("boom"));
    vi.mocked(api.listarContratos).mockRejectedValueOnce(new Error("boom"));

    render(<ContratosPage />);

    // ao falhar, sai do loading e cai no empty state (sem crash)
    await waitFor(() =>
      expect(
        screen.getByText(/nenhum contrato cadastrado/i),
      ).toBeInTheDocument(),
    );
    expect(toast.error).toHaveBeenCalledWith("boom");
    expect(api.criarContrato).not.toHaveBeenCalled();
  });

  it("valida cliente obrigatorio (sem chamar a API) ao submeter sem selecionar cliente", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.listarContratos).mockResolvedValueOnce([]);

    const user = userEvent.setup();
    render(<ContratosPage />);

    await waitFor(() => expect(api.listarContratos).toHaveBeenCalled());

    // Preenche descricao e valor (inputs nativos `required`) para que o submit
    // chegue ao handler; o cliente (Radix Select) fica vazio -> dispara a
    // validacao manual `!clienteId`.
    await user.type(
      screen.getByPlaceholderText("Seguro frota"),
      "Consorcio maquinas",
    );
    await user.type(screen.getByPlaceholderText("780.00"), "500,00");

    await user.click(
      screen.getByRole("button", { name: /cadastrar contrato/i }),
    );

    expect(toast.error).toHaveBeenCalledWith(
      "Preencha cliente, descrição e valor",
    );
    expect(api.criarContrato).not.toHaveBeenCalled();
  });
});
