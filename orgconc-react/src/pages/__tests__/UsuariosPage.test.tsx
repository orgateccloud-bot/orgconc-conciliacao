import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { UsuariosPage } from "@/pages/UsuariosPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarOrgs: vi.fn(),
    criarOrg: vi.fn(),
    listarUsuarios: vi.fn(),
    criarUsuario: vi.fn(),
    resetarSenhaUsuario: vi.fn(),
  };
});

// useAuth é mockado: a página exige role "admin" (caso contrário <Navigate>).
const mockUseAuth = vi.fn();
vi.mock("@/lib/auth", () => ({
  useAuth: () => mockUseAuth(),
}));

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

const ADMIN = { sub: "u-admin", email: "admin@orgatec.com", role: "admin" } as api.UserMe;

const ORG: api.OrgAdmin = {
  id: "org-1",
  nome: "Acme Ltda",
  cnpj: "11.222.333/0001-81",
  plano: "pro",
  ativo: true,
  criado_em: "2026-01-01T00:00:00Z",
};

const USUARIO: api.UsuarioAdmin = {
  id: "user-1",
  email: "joao@acme.com",
  nome: "João Silva",
  role: "user",
  ativo: true,
  criado_em: "2026-02-15T12:00:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <UsuariosPage />
    </MemoryRouter>,
  );
}

describe("UsuariosPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockUseAuth.mockReturnValue({
      user: ADMIN,
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
    });
  });

  it("mostra o hero e o formulario de nova organizacao ao montar", async () => {
    vi.mocked(api.listarOrgs).mockResolvedValueOnce([]);
    renderPage();

    expect(screen.getByText("Nova organização")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /criar organização/i }),
    ).toBeInTheDocument();
    // useEffect inicial dispara o fetch de orgs.
    await waitFor(() => expect(api.listarOrgs).toHaveBeenCalledTimes(1));
  });

  it("lista as organizacoes e os usuarios retornados pela API", async () => {
    vi.mocked(api.listarOrgs).mockResolvedValueOnce([ORG]);
    vi.mocked(api.listarUsuarios).mockResolvedValueOnce([USUARIO]);
    renderPage();

    // Carrega a primeira org e busca seus usuários automaticamente.
    await waitFor(() => expect(api.listarUsuarios).toHaveBeenCalledWith("org-1"));
    await waitFor(() =>
      expect(screen.getByText("joao@acme.com")).toBeInTheDocument(),
    );
    expect(screen.getByText("João Silva")).toBeInTheDocument();
    // Badge de papel "user" → label "Usuário".
    expect(screen.getByText("Usuário")).toBeInTheDocument();
    expect(screen.getByText("Ativo")).toBeInTheDocument();
    // Data criada exibida só com os 10 primeiros caracteres (yyyy-mm-dd).
    expect(screen.getByText("2026-02-15")).toBeInTheDocument();
    // Contador no cabeçalho da tabela.
    expect(screen.getByText("1 usuário(s)")).toBeInTheDocument();
  });

  it("mostra empty state quando nao ha nenhuma organizacao", async () => {
    vi.mocked(api.listarOrgs).mockResolvedValueOnce([]);
    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/nenhuma organização ainda/i),
      ).toBeInTheDocument(),
    );
    // Sem org selecionada → tabela mostra o prompt de seleção.
    expect(
      screen.getByText(/selecione uma organização para ver os usuários/i),
    ).toBeInTheDocument();
    // Sem org, não busca usuários.
    expect(api.listarUsuarios).not.toHaveBeenCalled();
  });

  it("mostra empty state de usuarios quando a org nao tem nenhum", async () => {
    vi.mocked(api.listarOrgs).mockResolvedValueOnce([ORG]);
    vi.mocked(api.listarUsuarios).mockResolvedValueOnce([]);
    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/nenhum usuário nesta organização ainda/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("0 usuário(s)")).toBeInTheDocument();
  });

  it("nao quebra e avisa via toast quando listar organizacoes falha", async () => {
    vi.mocked(api.listarOrgs).mockRejectedValueOnce(new Error("500 boom"));
    renderPage();

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("500 boom"));
    // Página segue renderizada (form de nova org continua presente).
    expect(screen.getByText("Nova organização")).toBeInTheDocument();
  });

  it("nao quebra e avisa via toast quando listar usuarios falha", async () => {
    vi.mocked(api.listarOrgs).mockResolvedValueOnce([ORG]);
    vi.mocked(api.listarUsuarios).mockRejectedValueOnce(new Error("falhou users"));
    renderPage();

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("falhou users"));
    expect(screen.getByText("Nova organização")).toBeInTheDocument();
  });

  it("redireciona para o dashboard quando o usuario nao e admin", async () => {
    mockUseAuth.mockReturnValue({
      user: { sub: "u2", email: "user@acme.com", role: "user" } as api.UserMe,
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
    });
    vi.mocked(api.listarOrgs).mockResolvedValue([]);

    renderPage();
    // <Navigate> substitui o conteúdo — o form de nova org não é renderizado.
    expect(screen.queryByText("Nova organização")).not.toBeInTheDocument();
  });

  it("cria organizacao e recarrega a lista ao submeter o formulario", async () => {
    const user = userEvent.setup();
    // 1ª carga: vazio. Após criar: recarrega com a nova org.
    vi.mocked(api.listarOrgs)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([ORG]);
    vi.mocked(api.listarUsuarios).mockResolvedValue([]);
    vi.mocked(api.criarOrg).mockResolvedValueOnce({
      id: "org-1",
      nome: "Acme Ltda",
      plano: "basico",
    });

    renderPage();
    await waitFor(() => expect(api.listarOrgs).toHaveBeenCalledTimes(1));

    const nomeInput = screen.getByPlaceholderText("Razão social");
    await user.type(nomeInput, "Acme Ltda");
    await user.click(screen.getByRole("button", { name: /criar organização/i }));

    await waitFor(() =>
      expect(api.criarOrg).toHaveBeenCalledWith(
        expect.objectContaining({ nome: "Acme Ltda", plano: "basico" }),
      ),
    );
    expect(toastSuccess).toHaveBeenCalledWith("Organização criada");
    // Recarrega selecionando a nova org.
    await waitFor(() => expect(api.listarOrgs).toHaveBeenCalledTimes(2));
  });

  it("valida senha curta ao cadastrar usuario (sem chamar a API)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarOrgs).mockResolvedValueOnce([ORG]);
    vi.mocked(api.listarUsuarios).mockResolvedValue([USUARIO]);

    renderPage();
    await waitFor(() => expect(api.listarUsuarios).toHaveBeenCalledWith("org-1"));

    await user.type(
      screen.getByPlaceholderText("usuario@empresa.com"),
      "novo@acme.com",
    );
    // Senha com 8+ chars habilita o botão; usamos a validação por submit do form.
    await user.type(screen.getByPlaceholderText("••••••••"), "1234567");

    // Botão fica desabilitado com senha < 8, então a API nunca é chamada.
    expect(
      screen.getByRole("button", { name: /cadastrar usuário/i }),
    ).toBeDisabled();
    expect(api.criarUsuario).not.toHaveBeenCalled();
  });

  it("cadastra usuario e recarrega a lista quando os dados sao validos", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarOrgs).mockResolvedValueOnce([ORG]);
    vi.mocked(api.listarUsuarios).mockResolvedValue([]);
    vi.mocked(api.criarUsuario).mockResolvedValueOnce({
      id: "user-9",
      email: "novo@acme.com",
      org_id: "org-1",
      role: "user",
    });

    renderPage();
    await waitFor(() => expect(api.listarUsuarios).toHaveBeenCalledWith("org-1"));

    await user.type(
      screen.getByPlaceholderText("usuario@empresa.com"),
      "novo@acme.com",
    );
    await user.type(screen.getByPlaceholderText("••••••••"), "senhaforte123");
    await user.click(
      screen.getByRole("button", { name: /cadastrar usuário/i }),
    );

    await waitFor(() =>
      expect(api.criarUsuario).toHaveBeenCalledWith(
        expect.objectContaining({
          email: "novo@acme.com",
          senha: "senhaforte123",
          org_id: "org-1",
          role: "user",
        }),
      ),
    );
    expect(toastSuccess).toHaveBeenCalledWith("Usuário cadastrado");
  });

  it("abre o dialog de reset de senha ao clicar no botao da linha", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarOrgs).mockResolvedValueOnce([ORG]);
    vi.mocked(api.listarUsuarios).mockResolvedValue([USUARIO]);

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("joao@acme.com")).toBeInTheDocument(),
    );

    await user.click(screen.getByTitle("Redefinir senha"));

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Redefinir senha" }),
      ).toBeInTheDocument(),
    );
    // O e-mail do usuário aparece no corpo do dialog.
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("joao@acme.com");
  });

  it("confirma o reset de senha e mostra toast de sucesso", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarOrgs).mockResolvedValueOnce([ORG]);
    vi.mocked(api.listarUsuarios).mockResolvedValue([USUARIO]);
    vi.mocked(api.resetarSenhaUsuario).mockResolvedValueOnce({
      detail: "ok",
    });

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("joao@acme.com")).toBeInTheDocument(),
    );

    await user.click(screen.getByTitle("Redefinir senha"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    // Há dois inputs com este placeholder (form de usuário + dialog); escopa no dialog.
    const dialog = screen.getByRole("dialog");
    await user.type(
      within(dialog).getByPlaceholderText("••••••••"),
      "novasenha123",
    );
    await user.click(
      within(dialog).getByRole("button", { name: /^redefinir senha$/i }),
    );

    await waitFor(() =>
      expect(api.resetarSenhaUsuario).toHaveBeenCalledWith(
        "user-1",
        "novasenha123",
      ),
    );
    expect(toastSuccess).toHaveBeenCalledWith(
      "Senha de joao@acme.com redefinida — sessões revogadas",
    );
  });
});
