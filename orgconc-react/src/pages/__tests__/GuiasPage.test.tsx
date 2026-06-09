import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GuiasPage } from "@/pages/GuiasPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    listarGuias: vi.fn(),
    criarGuia: vi.fn(),
  };
});

import * as api from "@/lib/api";

const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    error: (...args: unknown[]) => toastError(...args),
    success: (...args: unknown[]) => toastSuccess(...args),
  },
}));

const CLIENTE = {
  id: "c1",
  nome: "Acme Ltda",
  cnpj: "11222333000181",
  plano: "pro",
  ativo: true,
} as api.Cliente;

const GUIA = {
  id: "g1",
  cliente_id: "c1",
  tipo: "DARF",
  codigo_receita: "0220",
  valor: 1234.56,
  competencia: "2026-05",
  data_vencimento: "2026-06-20",
  conta_contabil: "2.1.3.01.001",
  ativo: true,
  criado_em: "2026-05-01T00:00:00Z",
} as api.Guia;

function renderGuias() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <GuiasPage />
    </QueryClientProvider>,
  );
}

describe("GuiasPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("dispara o fetch de guias e clientes ao montar", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.listarGuias).mockResolvedValue([]);

    renderGuias();

    await waitFor(() => expect(api.listarGuias).toHaveBeenCalledTimes(1));
    expect(api.listarClientes).toHaveBeenCalled();
  });

  it("mostra titulo e formulario de nova guia", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([]);
    vi.mocked(api.listarGuias).mockResolvedValue([]);

    renderGuias();

    expect(screen.getByText("Nova guia")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /cadastrar guia/i }),
    ).toBeInTheDocument();
    await waitFor(() => expect(api.listarGuias).toHaveBeenCalled());
  });

  it("renderiza as guias retornadas pela API", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.listarGuias).mockResolvedValue([GUIA]);

    renderGuias();

    // valor formatado, competencia, vencimento, conta — celulas unicas da tabela
    await waitFor(() =>
      expect(screen.getByText("1.234,56")).toBeInTheDocument(),
    );
    expect(screen.getByText("2026-05")).toBeInTheDocument();
    expect(screen.getByText("2026-06-20")).toBeInTheDocument();
    expect(screen.getByText("2.1.3.01.001")).toBeInTheDocument();
    // resolve o nome do cliente a partir do id; "Acme Ltda" tambem e opcao
    // do Select de cliente, por isso usamos getAllByText (>1 ocorrencia).
    expect(screen.getAllByText("Acme Ltda").length).toBeGreaterThan(0);
    // "DARF" aparece no badge da linha e tambem como opcao do Select de tipo
    expect(screen.getAllByText("DARF").length).toBeGreaterThan(0);
  });

  it("mostra empty state quando nao ha guias", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([]);
    vi.mocked(api.listarGuias).mockResolvedValue([]);

    renderGuias();

    await waitFor(() =>
      expect(screen.getByText(/nenhuma guia cadastrada/i)).toBeInTheDocument(),
    );
  });

  it("nao quebra e avisa via toast quando o fetch de guias falha", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([]);
    vi.mocked(api.listarGuias).mockRejectedValue(new Error("boom"));

    renderGuias();

    // erro tratado: cai no empty state (sem guias) e dispara toast.error
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("boom"));
    expect(screen.getByText(/nenhuma guia cadastrada/i)).toBeInTheDocument();
  });

  it("filtra a lista pela busca (tipo/competencia/valor)", async () => {
    const outra = {
      ...GUIA,
      id: "g2",
      tipo: "DAS",
      competencia: "2026-04",
      valor: 99.9,
    } as api.Guia;
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.listarGuias).mockResolvedValue([GUIA, outra]);

    renderGuias();

    // Usa as competencias (so aparecem na tabela) para identificar cada linha,
    // pois "DARF"/"DAS" colidem com as opcoes do Select de tipo.
    await waitFor(() => expect(screen.getByText("2026-05")).toBeInTheDocument());
    expect(screen.getByText("2026-04")).toBeInTheDocument();

    const user = userEvent.setup();
    const busca = screen.getByPlaceholderText(
      /buscar por tipo, competência ou valor/i,
    );
    // filtra pela competencia da primeira guia -> some a segunda linha
    await user.type(busca, "2026-05");

    await waitFor(() =>
      expect(screen.queryByText("2026-04")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("2026-05")).toBeInTheDocument();
  });

  it("avisa quando o cliente nao foi selecionado no submit", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.listarGuias).mockResolvedValue([]);

    renderGuias();
    await waitFor(() => expect(api.listarGuias).toHaveBeenCalled());

    const user = userEvent.setup();
    // Preenche o valor (input `required`) mas NAO seleciona cliente, para
    // alcancar a validacao `if (!clienteId || !valor)` em salvar(). Sem valor,
    // a validacao nativa do HTML bloquearia o submit antes do handler rodar.
    await user.type(screen.getByPlaceholderText("1234.56"), "100,00");
    await user.click(screen.getByRole("button", { name: /cadastrar guia/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Preencha cliente e valor"),
    );
    expect(api.criarGuia).not.toHaveBeenCalled();
  });
});
