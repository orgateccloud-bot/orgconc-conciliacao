import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfiguracoesPage } from "@/pages/ConfiguracoesPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, fetchHealth: vi.fn() };
});

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/theme", () => ({
  useTheme: vi.fn(),
}));

import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

const USER = {
  sub: "user-1",
  email: "auditor@orgconc.com",
  role: "admin",
} as api.UserMe;

const HEALTH = {
  status: "ok",
  versao: "1.2.3",
  banco_dados: "ok",
  api_key_configured: true,
} as api.HealthResponse;

function setAuth(user: api.UserMe | null = USER) {
  vi.mocked(useAuth).mockReturnValue({
    user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  });
}

const toggleSpy = vi.fn();

function setTheme(tema: "light" | "dark" = "light") {
  vi.mocked(useTheme).mockReturnValue({ tema, toggle: toggleSpy });
}

describe("ConfiguracoesPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    toggleSpy.mockReset();
    setAuth();
    setTheme();
  });

  it("dispara fetchHealth ao montar", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    render(<ConfiguracoesPage />);
    await waitFor(() => expect(api.fetchHealth).toHaveBeenCalledTimes(1));
  });

  it("renderiza titulo e secoes principais", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    render(<ConfiguracoesPage />);
    expect(screen.getByText("Conta")).toBeInTheDocument();
    expect(screen.getByText("Interface")).toBeInTheDocument();
    expect(screen.getByText("Status do servidor")).toBeInTheDocument();
  });

  it("mostra dados da conta do usuario autenticado", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    render(<ConfiguracoesPage />);
    expect(screen.getByText("auditor@orgconc.com")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("usa sub como fallback quando nao ha email e exibe — sem papel", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    setAuth({ sub: "fallback-sub", role: "" } as api.UserMe);
    render(<ConfiguracoesPage />);
    expect(screen.getByText("fallback-sub")).toBeInTheDocument();
    // role vazio cai no fallback "—"
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renderiza status do servidor com os valores retornados", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    render(<ConfiguracoesPage />);
    await waitFor(() => expect(screen.getByText("1.2.3")).toBeInTheDocument());
    expect(screen.getByText("Configurada")).toBeInTheDocument();
    // Status e Banco aparecem como "ok" (dois itens)
    expect(screen.getAllByText("ok").length).toBeGreaterThanOrEqual(2);
  });

  it("mostra 'Ausente' quando a API Claude nao esta configurada", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce({
      ...HEALTH,
      api_key_configured: false,
    });
    render(<ConfiguracoesPage />);
    await waitFor(() => expect(screen.getByText("Ausente")).toBeInTheDocument());
  });

  it("mostra mensagem de servidor indisponivel quando fetchHealth falha", async () => {
    vi.mocked(api.fetchHealth).mockRejectedValueOnce(new Error("500"));
    render(<ConfiguracoesPage />);
    await waitFor(() =>
      expect(screen.getByText("Servidor indisponível.")).toBeInTheDocument(),
    );
  });

  it("exibe o tema atual (claro) e o botao para mudar para escuro", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    setTheme("light");
    render(<ConfiguracoesPage />);
    expect(screen.getByText("Claro")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /mudar para escuro/i }),
    ).toBeInTheDocument();
  });

  it("exibe o tema atual (escuro) e o botao para mudar para claro", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    setTheme("dark");
    render(<ConfiguracoesPage />);
    expect(screen.getByText("Escuro")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /mudar para claro/i }),
    ).toBeInTheDocument();
  });

  it("chama toggle ao clicar no botao de tema", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    setTheme("light");
    const user = userEvent.setup();
    render(<ConfiguracoesPage />);
    await user.click(screen.getByRole("button", { name: /mudar para escuro/i }));
    expect(toggleSpy).toHaveBeenCalledTimes(1);
  });

  it("mantem o botao de atualizar senha desabilitado por padrao", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    render(<ConfiguracoesPage />);
    expect(
      screen.getByRole("button", { name: /atualizar senha/i }),
    ).toBeDisabled();
  });

  it("mostra erro de validacao quando as senhas nao coincidem", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    const user = userEvent.setup();
    const { container } = render(<ConfiguracoesPage />);
    const inputs = container.querySelectorAll('input[type="password"]');
    await user.type(inputs[0] as HTMLInputElement, "12345678");
    await user.type(inputs[1] as HTMLInputElement, "9999");
    expect(
      screen.getByText("As senhas não coincidem ou são muito curtas."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /atualizar senha/i }),
    ).toBeDisabled();
  });

  it("habilita o botao quando as senhas coincidem e tem 8+ caracteres", async () => {
    vi.mocked(api.fetchHealth).mockResolvedValueOnce(HEALTH);
    const user = userEvent.setup();
    const { container } = render(<ConfiguracoesPage />);
    const inputs = container.querySelectorAll('input[type="password"]');
    await user.type(inputs[0] as HTMLInputElement, "senhaforte1");
    await user.type(inputs[1] as HTMLInputElement, "senhaforte1");
    expect(
      screen.queryByText("As senhas não coincidem ou são muito curtas."),
    ).not.toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /atualizar senha/i }),
      ).toBeEnabled(),
    );
  });

  it("mostra skeleton de carregamento enquanto health nao resolve", async () => {
    let resolve!: (v: api.HealthResponse) => void;
    vi.mocked(api.fetchHealth).mockReturnValueOnce(
      new Promise<api.HealthResponse>((r) => {
        resolve = r;
      }),
    );
    const { container } = render(<ConfiguracoesPage />);
    // Enquanto pendente: nem dados nem erro
    expect(screen.queryByText("Servidor indisponível.")).not.toBeInTheDocument();
    expect(container.querySelectorAll(".animate-pulse").length).toBe(4);
    resolve(HEALTH);
    await waitFor(() => expect(screen.getByText("1.2.3")).toBeInTheDocument());
  });
});
