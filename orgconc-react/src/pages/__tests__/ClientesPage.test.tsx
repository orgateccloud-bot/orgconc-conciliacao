import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ClientesPage } from "@/pages/ClientesPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    criarCliente: vi.fn(),
    atualizarCliente: vi.fn(),
    listarConciliacoesDoCliente: vi.fn(),
    invalidarCacheClientes: vi.fn(),
  };
});

// sonner: silencia toasts e permite asserções de erro/sucesso.
const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    error: (...args: unknown[]) => toastError(...args),
    success: (...args: unknown[]) => toastSuccess(...args),
  },
}));

import * as api from "@/lib/api";

const CLIENTE = {
  id: "c1",
  nome: "Acme Ltda",
  cnpj: "11222333000181",
  plano: "pro",
  ativo: true,
} as api.Cliente;

// CNPJ válido (dígitos verificadores corretos) para o caminho feliz do form.
const CNPJ_VALIDO = "11444777000161";

const CONCILIACAO = {
  report_id: "rpt_abcdef0123456789",
  modo: "fiscal",
  total_transacoes: 42,
  total_anomalias: 3,
  criado_em: "2026-02-15T12:00:00Z",
  exports: {
    html: "https://x/rel.html",
    xlsx: "https://x/rel.xlsx",
    pdf: "https://x/rel.pdf",
  },
} as api.ConciliacaoMeta;

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

  // ── Listagem: formatação de badges, contador e CNPJ ausente ──────────────

  it("renderiza plano, status e contador de resultados na tabela", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([
      CLIENTE,
      {
        id: "c2",
        nome: "Beta SA",
        plano: "enterprise",
        ativo: false,
      } as api.Cliente,
    ]);
    render(<ClientesPage />);

    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());
    // Escopa na tabela: o <Select> do form repete os labels de plano.
    const tabela = screen.getByRole("table");
    // Labels de plano traduzidos.
    expect(within(tabela).getByText("Pro")).toBeInTheDocument();
    expect(within(tabela).getByText("Enterprise")).toBeInTheDocument();
    // Status: ativo true vs false.
    expect(within(tabela).getByText("Ativo")).toBeInTheDocument();
    expect(within(tabela).getByText("Inativo")).toBeInTheDocument();
    // Cliente sem CNPJ exibe travessão.
    expect(within(tabela).getByText("—")).toBeInTheDocument();
    // Contador no cabeçalho da busca.
    expect(screen.getByText("2 resultado(s)")).toBeInTheDocument();
  });

  it("usa o valor cru do plano quando nao ha label mapeado", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([
      { id: "c9", nome: "Gamma", plano: "custom", ativo: true } as api.Cliente,
    ]);
    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Gamma")).toBeInTheDocument());
    // Sem entrada em PLANO_LABELS → mostra a chave crua.
    expect(screen.getByText("custom")).toBeInTheDocument();
  });

  it("avisa via toast e nao quebra quando listar clientes falha", async () => {
    vi.mocked(api.listarClientes).mockRejectedValueOnce(new Error("500 boom"));
    render(<ClientesPage />);
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("500 boom"));
    // Form de novo cliente segue presente.
    expect(screen.getByText("Novo cliente")).toBeInTheDocument();
  });

  it("usa mensagem generica quando o erro de listagem nao e Error", async () => {
    vi.mocked(api.listarClientes).mockRejectedValueOnce("estourou");
    render(<ClientesPage />);
    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Falha ao listar clientes"),
    );
  });

  // ── Busca / filtro ───────────────────────────────────────────────────────

  it("filtra clientes por nome e mostra empty state especifico da busca", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([
      CLIENTE,
      { id: "c2", nome: "Beta SA", plano: "basico", ativo: true } as api.Cliente,
    ]);
    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    const busca = screen.getByPlaceholderText(/buscar por nome ou cnpj/i);
    await user.type(busca, "beta");

    expect(screen.queryByText("Acme Ltda")).not.toBeInTheDocument();
    expect(screen.getByText("Beta SA")).toBeInTheDocument();
    expect(screen.getByText("1 resultado(s)")).toBeInTheDocument();

    // Busca sem resultados → empty state específico de busca.
    await user.clear(busca);
    await user.type(busca, "inexistente");
    expect(
      screen.getByText(/nenhum cliente encontrado para esta busca/i),
    ).toBeInTheDocument();
  });

  it("filtra clientes pelo CNPJ", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([
      CLIENTE,
      { id: "c2", nome: "Beta SA", cnpj: "99888777000166", plano: "basico", ativo: true } as api.Cliente,
    ]);
    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText(/buscar por nome ou cnpj/i), "11222333");
    expect(screen.getByText("Acme Ltda")).toBeInTheDocument();
    expect(screen.queryByText("Beta SA")).not.toBeInTheDocument();
  });

  // ── Criação ──────────────────────────────────────────────────────────────

  it("mantem o botao desabilitado enquanto o nome estiver vazio", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ClientesPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());
    expect(
      screen.getByRole("button", { name: /cadastrar cliente/i }),
    ).toBeDisabled();
  });

  it("rejeita CNPJ invalido sem chamar a API", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ClientesPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    await user.type(screen.getByPlaceholderText("Razão social ou nome"), "Nova Empresa");
    await user.type(
      screen.getByPlaceholderText("00.000.000/0001-00"),
      "11111111111111",
    );
    await user.click(screen.getByRole("button", { name: /cadastrar cliente/i }));

    expect(toastError).toHaveBeenCalledWith(
      "CNPJ inválido — verifique os dígitos verificadores",
    );
    expect(api.criarCliente).not.toHaveBeenCalled();
  });

  it("cria cliente, invalida o cache e recarrega a lista", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.criarCliente).mockResolvedValueOnce(CLIENTE);

    render(<ClientesPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));

    await user.type(screen.getByPlaceholderText("Razão social ou nome"), "Acme Ltda");
    await user.type(screen.getByPlaceholderText("00.000.000/0001-00"), CNPJ_VALIDO);
    await user.click(screen.getByRole("button", { name: /cadastrar cliente/i }));

    await waitFor(() =>
      expect(api.criarCliente).toHaveBeenCalledWith(
        expect.objectContaining({
          nome: "Acme Ltda",
          cnpj: CNPJ_VALIDO,
          plano: "basico",
        }),
      ),
    );
    expect(api.invalidarCacheClientes).toHaveBeenCalledTimes(1);
    expect(toastSuccess).toHaveBeenCalledWith("Cliente cadastrado");
    // Recarrega a lista após criar.
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(2));
  });

  it("cria cliente sem CNPJ enviando campos opcionais como undefined", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);
    vi.mocked(api.criarCliente).mockResolvedValueOnce(CLIENTE);

    render(<ClientesPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));

    await user.type(screen.getByPlaceholderText("Razão social ou nome"), "Sem CNPJ");
    await user.click(screen.getByRole("button", { name: /cadastrar cliente/i }));

    await waitFor(() =>
      expect(api.criarCliente).toHaveBeenCalledWith(
        expect.objectContaining({
          nome: "Sem CNPJ",
          cnpj: undefined,
          email: undefined,
          telefone: undefined,
          plano: "basico",
        }),
      ),
    );
  });

  it("cria cliente enviando email e telefone preenchidos", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.criarCliente).mockResolvedValueOnce(CLIENTE);

    render(<ClientesPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));

    const form = screen.getByText("Novo cliente").closest("form")!;
    await user.type(screen.getByPlaceholderText("Razão social ou nome"), "Acme Ltda");
    await user.type(screen.getByPlaceholderText("00.000.000/0001-00"), CNPJ_VALIDO);
    // E-mail (type=email) e telefone disparam os onChange (linhas 225-229).
    // Labels não estão associados via htmlFor/id → selecionamos pelo DOM.
    await user.type(within(form).getByPlaceholderText("(11) 99999-9999"), "(11) 98888-7777");
    const emailInput = form.querySelector('input[type="email"]') as HTMLInputElement;
    await user.type(emailInput, "contato@acme.com");
    await user.click(screen.getByRole("button", { name: /cadastrar cliente/i }));

    await waitFor(() =>
      expect(api.criarCliente).toHaveBeenCalledWith(
        expect.objectContaining({
          nome: "Acme Ltda",
          cnpj: CNPJ_VALIDO,
          email: "contato@acme.com",
          telefone: "(11) 98888-7777",
        }),
      ),
    );
  });

  it("avisa via toast quando criar cliente falha", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    vi.mocked(api.criarCliente).mockRejectedValueOnce(new Error("duplicado"));

    render(<ClientesPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));

    await user.type(screen.getByPlaceholderText("Razão social ou nome"), "Acme Ltda");
    await user.click(screen.getByRole("button", { name: /cadastrar cliente/i }));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("duplicado"));
    // Não recarrega depois do erro (continua só a carga inicial).
    expect(api.listarClientes).toHaveBeenCalledTimes(1);
  });

  it("usa mensagem generica quando o erro de criacao nao e Error", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    vi.mocked(api.criarCliente).mockRejectedValueOnce("falha crua");

    render(<ClientesPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));

    await user.type(screen.getByPlaceholderText("Razão social ou nome"), "Acme Ltda");
    await user.click(screen.getByRole("button", { name: /cadastrar cliente/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Erro ao cadastrar"),
    );
  });

  // ── Edição ───────────────────────────────────────────────────────────────

  it("abre o dialog de edicao pre-preenchido ao clicar no lapis", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.click(screen.getByTitle("Editar cliente"));

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Editar cliente" }),
      ).toBeInTheDocument(),
    );
    const dialog = screen.getByRole("dialog");
    // Nome pré-preenchido com o valor do cliente.
    expect(within(dialog).getByDisplayValue("Acme Ltda")).toBeInTheDocument();
  });

  it("salva a edicao e recarrega a lista", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes)
      .mockResolvedValueOnce([CLIENTE])
      .mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.atualizarCliente).mockResolvedValueOnce(CLIENTE);

    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.click(screen.getByTitle("Editar cliente"));
    const dialog = await screen.findByRole("dialog");

    const nome = within(dialog).getByDisplayValue("Acme Ltda");
    await user.clear(nome);
    await user.type(nome, "Acme Renomeada");
    // E-mail e telefone do dialog disparam seus onChange (linhas 343-352).
    // Labels sem htmlFor → e-mail é o input[type=email]; telefone é o texto vazio restante.
    const editEmail = dialog.querySelector('input[type="email"]') as HTMLInputElement;
    await user.type(editEmail, "novo@acme.com");
    const textInputs = Array.from(
      dialog.querySelectorAll('input:not([type="email"])'),
    ) as HTMLInputElement[];
    const editTelefone = textInputs.find((el) => el.value === "")!;
    await user.type(editTelefone, "(11) 90000-0000");
    await user.click(
      within(dialog).getByRole("button", { name: /salvar alterações/i }),
    );

    await waitFor(() =>
      expect(api.atualizarCliente).toHaveBeenCalledWith(
        "c1",
        expect.objectContaining({
          nome: "Acme Renomeada",
          email: "novo@acme.com",
          telefone: "(11) 90000-0000",
          plano: "pro",
          ativo: true,
        }),
      ),
    );
    expect(toastSuccess).toHaveBeenCalledWith("Cliente atualizado");
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(2));
  });

  it("avisa via toast quando salvar edicao falha", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.atualizarCliente).mockRejectedValueOnce(new Error("conflito"));

    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.click(screen.getByTitle("Editar cliente"));
    const dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: /salvar alterações/i }),
    );

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("conflito"));
    // Não recarrega após falha.
    expect(api.listarClientes).toHaveBeenCalledTimes(1);
  });

  it("fecha o dialog de edicao ao cancelar sem chamar a API", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.click(screen.getByTitle("Editar cliente"));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /cancelar/i }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(api.atualizarCliente).not.toHaveBeenCalled();
  });

  it("pre-preenche edicao tratando email/telefone ausentes e ativo undefined", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([
      { id: "c3", nome: "Sem Contato", plano: "basico" } as api.Cliente,
    ]);
    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Sem Contato")).toBeInTheDocument());

    await user.click(screen.getByTitle("Editar cliente"));
    const dialog = await screen.findByRole("dialog");
    // Nome preenchido; e-mail/telefone caem para string vazia (sem crash).
    expect(within(dialog).getByDisplayValue("Sem Contato")).toBeInTheDocument();
  });

  // ── Detalhe (Sheet) + histórico ──────────────────────────────────────────

  it("abre o detalhe e lista o historico de conciliacoes", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.listarConciliacoesDoCliente).mockResolvedValueOnce([CONCILIACAO]);

    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.click(screen.getByText("Acme Ltda"));

    await waitFor(() =>
      expect(api.listarConciliacoesDoCliente).toHaveBeenCalledWith("c1"),
    );
    // Conteúdo do histórico: modo, contagem de tx e anomalias.
    await waitFor(() => expect(screen.getByText("fiscal")).toBeInTheDocument());
    expect(screen.getByText("42 tx")).toBeInTheDocument();
    expect(screen.getByText("3 anom.")).toBeInTheDocument();
    // report_id truncado nos 12 primeiros chars + reticências.
    expect(screen.getByText(/rpt_abcdef01…/)).toBeInTheDocument();
    // Três links de download (HTML/Excel/PDF).
    expect(screen.getByTitle("HTML")).toHaveAttribute("href", "https://x/rel.html");
    expect(screen.getByTitle("Excel")).toHaveAttribute("href", "https://x/rel.xlsx");
    expect(screen.getByTitle("PDF")).toHaveAttribute("href", "https://x/rel.pdf");
  });

  it("mostra empty state de historico quando nao ha conciliacoes", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.listarConciliacoesDoCliente).mockResolvedValueOnce([]);

    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.click(screen.getByText("Acme Ltda"));

    await waitFor(() =>
      expect(
        screen.getByText(/nenhuma conciliação vinculada a este cliente/i),
      ).toBeInTheDocument(),
    );
  });

  it("nao quebra o detalhe quando buscar historico falha (catch silencioso)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.listarConciliacoesDoCliente).mockRejectedValueOnce(
      new Error("db off"),
    );

    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.click(screen.getByText("Acme Ltda"));

    // Falha é engolida → cai no empty state, sem toast de erro.
    await waitFor(() =>
      expect(
        screen.getByText(/nenhuma conciliação vinculada a este cliente/i),
      ).toBeInTheDocument(),
    );
    expect(toastError).not.toHaveBeenCalled();
  });

  it("exibe anomalias em verde quando o total e zero", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.listarConciliacoesDoCliente).mockResolvedValueOnce([
      { ...CONCILIACAO, report_id: "rpt_zero000000000", total_anomalias: 0 } as api.ConciliacaoMeta,
    ]);

    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.click(screen.getByText("Acme Ltda"));

    await waitFor(() => expect(screen.getByText("0 anom.")).toBeInTheDocument());
  });

  it("clicar no lapis nao abre o detalhe (stopPropagation)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    render(<ClientesPage />);
    await waitFor(() => expect(screen.getByText("Acme Ltda")).toBeInTheDocument());

    await user.click(screen.getByTitle("Editar cliente"));

    // Abre o dialog de edição, mas NÃO o sheet de detalhe.
    await screen.findByRole("dialog");
    expect(api.listarConciliacoesDoCliente).not.toHaveBeenCalled();
  });
});
