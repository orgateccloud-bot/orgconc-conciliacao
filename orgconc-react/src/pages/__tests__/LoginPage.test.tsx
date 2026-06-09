import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "@/pages/LoginPage";

// useNavigate é espionado, mas o restante do react-router-dom (MemoryRouter)
// continua real para que o <LoginPage /> renderize dentro de um Router válido.
const navigateMock = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

// useAuth: forma REAL do contexto ({ user, loading, login, logout }).
const loginMock = vi.fn();
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    login: loginMock,
    logout: vi.fn(),
  }),
}));

// sonner não precisa de provider; mockamos para inspecionar os toasts.
const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

const LAST_LOGIN_KEY = "orgatec_last_login";

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
  });

  it("renderiza o formulario de login (titulo, campos e botao)", () => {
    renderLogin();
    expect(screen.getByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.getByLabelText("Senha")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /acessar painel/i })).toBeInTheDocument();
  });

  it("nao mostra 'Ultimo acesso' quando nao ha registro armazenado", () => {
    renderLogin();
    expect(screen.queryByText(/Último acesso:/i)).not.toBeInTheDocument();
  });

  it("mostra 'Ultimo acesso' quando ha um timestamp no localStorage", async () => {
    localStorage.setItem(LAST_LOGIN_KEY, "2026-01-15T10:30:00.000Z");
    renderLogin();
    await waitFor(() =>
      expect(screen.getByText(/Último acesso:/i)).toBeInTheDocument(),
    );
  });

  it("bloqueia o submit e avisa quando a senha tem menos de 8 caracteres", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("E-mail"), "voce@empresa.com");
    await user.type(screen.getByLabelText("Senha"), "1234567");
    await user.click(screen.getByRole("button", { name: /acessar painel/i }));

    expect(toastError).toHaveBeenCalledWith("Senha deve ter pelo menos 8 caracteres");
    expect(loginMock).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("faz login, grava o ultimo acesso e navega ao dashboard no caminho feliz", async () => {
    const user = userEvent.setup();
    loginMock.mockResolvedValueOnce(undefined);
    renderLogin();

    await user.type(screen.getByLabelText("E-mail"), "voce@empresa.com");
    await user.type(screen.getByLabelText("Senha"), "senhaforte123");
    await user.click(screen.getByRole("button", { name: /acessar painel/i }));

    await waitFor(() =>
      expect(loginMock).toHaveBeenCalledWith("voce@empresa.com", "senhaforte123"),
    );
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith("Sessão iniciada"),
    );
    expect(navigateMock).toHaveBeenCalledWith("/dashboard");
    expect(localStorage.getItem(LAST_LOGIN_KEY)).not.toBeNull();
  });

  it("mostra a mensagem de erro do backend e nao navega quando o login falha", async () => {
    const user = userEvent.setup();
    loginMock.mockRejectedValueOnce(new Error("Credenciais inválidas"));
    renderLogin();

    await user.type(screen.getByLabelText("E-mail"), "voce@empresa.com");
    await user.type(screen.getByLabelText("Senha"), "senhaforte123");
    await user.click(screen.getByRole("button", { name: /acessar painel/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Credenciais inválidas"),
    );
    expect(navigateMock).not.toHaveBeenCalled();
    expect(toastSuccess).not.toHaveBeenCalled();
    // o botão volta a ficar disponível após a falha (busy = false)
    expect(screen.getByRole("button", { name: /acessar painel/i })).not.toBeDisabled();
  });

  it("usa fallback 'Falha no login' quando o erro nao e uma Error", async () => {
    const user = userEvent.setup();
    loginMock.mockRejectedValueOnce("boom");
    renderLogin();

    await user.type(screen.getByLabelText("E-mail"), "voce@empresa.com");
    await user.type(screen.getByLabelText("Senha"), "senhaforte123");
    await user.click(screen.getByRole("button", { name: /acessar painel/i }));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Falha no login"));
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("alterna a visibilidade da senha pelo botao mostrar/ocultar", async () => {
    const user = userEvent.setup();
    renderLogin();

    const senha = screen.getByLabelText("Senha");
    expect(senha).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: "Mostrar senha" }));
    expect(senha).toHaveAttribute("type", "text");

    await user.click(screen.getByRole("button", { name: "Ocultar senha" }));
    expect(senha).toHaveAttribute("type", "password");
  });

  it("renderiza os selos de conformidade", () => {
    renderLogin();
    expect(screen.getByText("LGPD")).toBeInTheDocument();
    expect(screen.getByText("SOC 2")).toBeInTheDocument();
  });
});
