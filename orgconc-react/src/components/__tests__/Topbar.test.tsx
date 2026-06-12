import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Topbar } from "@/components/Topbar";

// Tema controlável por teste (light/dark) sem depender do ThemeProvider real.
const toggleMock = vi.fn();
let temaAtual: "light" | "dark" = "light";
vi.mock("@/lib/theme", () => ({
  useTheme: () => ({ tema: temaAtual, toggle: toggleMock }),
}));

// A CommandPalette (aberta pela Topbar) usa useAuth; entregamos um usuário nulo
// estável para não depender de rede/AuthProvider.
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: null, loading: false, login: vi.fn(), logout: vi.fn() }),
}));

function renderTopbar(props?: Partial<Parameters<typeof Topbar>[0]>) {
  return render(
    <MemoryRouter>
      <Topbar title="Visão Geral" dbStatus="online" {...props} />
    </MemoryRouter>,
  );
}

describe("Topbar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    temaAtual = "light";
  });

  describe("status do banco", () => {
    it("mostra 'conectado' quando online", () => {
      renderTopbar({ dbStatus: "online" });
      expect(screen.getByText("conectado")).toBeInTheDocument();
    });

    it("mostra 'offline' quando offline", () => {
      renderTopbar({ dbStatus: "offline" });
      expect(screen.getByText("offline")).toBeInTheDocument();
    });

    it("mostra 'conectando...' enquanto verifica", () => {
      renderTopbar({ dbStatus: "checking" });
      expect(screen.getByText("conectando...")).toBeInTheDocument();
    });
  });

  describe("menu lateral (hamburger)", () => {
    it("não renderiza o botão sem onToggleSidebar", () => {
      renderTopbar();
      expect(screen.queryByRole("button", { name: "Abrir menu" })).not.toBeInTheDocument();
    });

    it("dispara onToggleSidebar ao clicar no botão", async () => {
      const onToggleSidebar = vi.fn();
      const user = userEvent.setup();
      renderTopbar({ onToggleSidebar });
      await user.click(screen.getByRole("button", { name: "Abrir menu" }));
      expect(onToggleSidebar).toHaveBeenCalledTimes(1);
    });
  });

  describe("tema", () => {
    it("no tema claro oferece alternar para 'Tema escuro' e chama toggle", async () => {
      const user = userEvent.setup();
      renderTopbar();
      const botao = screen.getByRole("button", { name: "Tema escuro" });
      await user.click(botao);
      expect(toggleMock).toHaveBeenCalledTimes(1);
    });

    it("no tema escuro oferece alternar para 'Tema claro'", () => {
      temaAtual = "dark";
      renderTopbar();
      expect(screen.getByRole("button", { name: "Tema claro" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Tema escuro" })).not.toBeInTheDocument();
    });
  });

  describe("avatar do usuário", () => {
    it("não renderiza avatar sem userEmail", () => {
      renderTopbar();
      expect(screen.queryByTitle(/clique para sair/)).not.toBeInTheDocument();
    });

    it("mostra iniciais e dispara onLogout ao clicar", async () => {
      const onLogout = vi.fn();
      const user = userEvent.setup();
      renderTopbar({ userEmail: "bruno@orgatec.com", onLogout });
      const avatar = screen.getByTitle("bruno@orgatec.com — clique para sair");
      expect(avatar).toHaveTextContent("BR");
      await user.click(avatar);
      expect(onLogout).toHaveBeenCalledTimes(1);
    });
  });

  describe("notificações", () => {
    it("o sino fica desabilitado (em breve)", () => {
      renderTopbar();
      expect(screen.getByRole("button", { name: "Notificações" })).toBeDisabled();
    });
  });

  describe("paleta de navegação (⌘K)", () => {
    it("abre a CommandPalette ao clicar no botão de busca", async () => {
      const user = userEvent.setup();
      renderTopbar();
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      await user.click(
        screen.getByRole("button", { name: "Buscar e navegar (atalho Ctrl ou Cmd + K)" }),
      );
      expect(screen.getByRole("dialog", { name: "Buscar e navegar" })).toBeInTheDocument();
    });

    it("Ctrl+K abre e fecha a paleta (toggle)", () => {
      renderTopbar();
      fireEvent.keyDown(window, { key: "k", ctrlKey: true });
      expect(screen.getByRole("dialog", { name: "Buscar e navegar" })).toBeInTheDocument();
      fireEvent.keyDown(window, { key: "k", ctrlKey: true });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("Cmd+K (metaKey) também abre a paleta", () => {
      renderTopbar();
      fireEvent.keyDown(window, { key: "K", metaKey: true });
      expect(screen.getByRole("dialog", { name: "Buscar e navegar" })).toBeInTheDocument();
    });

    it("'k' sem modificador não abre a paleta", () => {
      renderTopbar();
      fireEvent.keyDown(window, { key: "k" });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("Escape dentro da paleta fecha via onClose", async () => {
      const user = userEvent.setup();
      renderTopbar();
      fireEvent.keyDown(window, { key: "k", ctrlKey: true });
      const input = screen.getByLabelText("Buscar telas");
      await user.type(input, "{Escape}");
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
