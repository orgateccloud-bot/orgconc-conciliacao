import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { CommandPalette } from "@/components/CommandPalette";
import type { UserMe } from "@/lib/api";

// O CommandPalette navega via useNavigate; espionamos a navegação real do router.
const navigateMock = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

// O componente lê o usuário de useAuth (forma real: { user, loading, login, logout }).
// O filtro adminOnly depende de user?.role === "admin".
const authMock = vi.fn();
vi.mock("@/lib/auth", () => ({
  useAuth: () => authMock(),
}));

const USER_COMUM: UserMe = { sub: "u1", email: "user@org.com", role: "user" };
const USER_ADMIN: UserMe = { sub: "a1", email: "admin@org.com", role: "admin" };

function authState(user: UserMe | null) {
  return { user, loading: false, login: vi.fn(), logout: vi.fn() };
}

function renderPalette(props: { open: boolean; onClose: () => void }) {
  return render(
    <MemoryRouter>
      <CommandPalette {...props} />
    </MemoryRouter>,
  );
}

describe("CommandPalette", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    authMock.mockReturnValue(authState(USER_COMUM));
  });

  it("não renderiza nada quando open=false", () => {
    const { container } = renderPalette({ open: false, onClose: vi.fn() });
    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renderiza o diálogo e o input de busca quando open=true", () => {
    renderPalette({ open: true, onClose: vi.fn() });
    expect(screen.getByRole("dialog", { name: "Buscar e navegar" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ir para…")).toBeInTheDocument();
    expect(screen.getByLabelText("Buscar telas")).toBeInTheDocument();
  });

  it("lista os destinos reais para um usuário comum (sem entradas adminOnly)", () => {
    renderPalette({ open: true, onClose: vi.fn() });
    // Destinos com rota real, presentes para qualquer usuário.
    expect(screen.getByText("Visão Geral")).toBeInTheDocument();
    expect(screen.getByText("Upload de Extratos")).toBeInTheDocument();
    expect(screen.getByText("Laudo Integrado")).toBeInTheDocument();
    expect(screen.getByText("Configurações")).toBeInTheDocument();
    // adminOnly NÃO aparece para usuário comum.
    expect(screen.queryByText("Usuários & Organizações")).not.toBeInTheDocument();
  });

  it("mostra a entrada adminOnly quando o usuário é admin", () => {
    authMock.mockReturnValue(authState(USER_ADMIN));
    renderPalette({ open: true, onClose: vi.fn() });
    expect(screen.getByText("Usuários & Organizações")).toBeInTheDocument();
  });

  it("filtra os destinos pelo texto digitado (label e grupo)", async () => {
    const user = userEvent.setup();
    renderPalette({ open: true, onClose: vi.fn() });
    const input = screen.getByLabelText("Buscar telas");
    await user.type(input, "laudo");
    await waitFor(() => expect(screen.getByText("Laudo Integrado")).toBeInTheDocument());
    // Outros destinos somem do resultado filtrado.
    expect(screen.queryByText("Visão Geral")).not.toBeInTheDocument();
  });

  it("filtra também por grupo (ex.: 'Fiscal')", async () => {
    const user = userEvent.setup();
    renderPalette({ open: true, onClose: vi.fn() });
    await user.type(screen.getByLabelText("Buscar telas"), "fiscal");
    await waitFor(() => expect(screen.getByText("Laudo Integrado")).toBeInTheDocument());
    expect(screen.getByText("Conformidade Fiscal")).toBeInTheDocument();
    // Um destino de outro grupo não deve sobreviver ao filtro.
    expect(screen.queryByText("Upload de Extratos")).not.toBeInTheDocument();
  });

  it("mostra o empty state 'Nada encontrado' quando o filtro não casa nada", async () => {
    const user = userEvent.setup();
    renderPalette({ open: true, onClose: vi.fn() });
    await user.type(screen.getByLabelText("Buscar telas"), "zzznaoexiste");
    await waitFor(() => expect(screen.getByText("Nada encontrado")).toBeInTheDocument());
  });

  it("navega e fecha ao clicar em um destino", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderPalette({ open: true, onClose });
    await user.click(screen.getByText("Clientes"));
    expect(navigateMock).toHaveBeenCalledWith("/clientes");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("navega com Enter para o destino selecionado pela seta para baixo", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderPalette({ open: true, onClose });
    const input = screen.getByLabelText("Buscar telas");
    input.focus();
    // sel começa em 0 (Visão Geral -> /dashboard); uma seta para baixo seleciona o 2º item.
    await user.keyboard("{ArrowDown}{Enter}");
    expect(navigateMock).toHaveBeenCalledWith("/upload");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("fecha ao pressionar Escape no input", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderPalette({ open: true, onClose });
    const input = screen.getByLabelText("Buscar telas");
    input.focus();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("fecha ao clicar no backdrop (fora do diálogo)", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderPalette({ open: true, onClose });
    // O backdrop é o elemento role="presentation"; clicá-lo fecha.
    await user.click(screen.getByRole("presentation"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
