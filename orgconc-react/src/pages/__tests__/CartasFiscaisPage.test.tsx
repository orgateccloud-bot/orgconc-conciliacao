import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CartasFiscaisPage } from "@/pages/CartasFiscaisPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    fiscalListarCartas: vi.fn(),
    fiscalGerarCarta: vi.fn(),
  };
});

import * as api from "@/lib/api";
import { toast } from "sonner";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Radix Select usa APIs de ponteiro que o jsdom não implementa.
beforeEach(() => {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }
});

const CLIENTE = {
  id: "c1",
  nome: "Acme Ltda",
  cnpj: "11222333000181",
  plano: "pro",
  ativo: true,
} as api.Cliente;

const CARTA_ITEM = {
  id: "carta-1",
  versao: "v3",
  risco_total: 12345.67,
  total_fornecedores: 5,
  payload_hash: "abcdef0123456789deadbeef0011",
  gerado_em: "2026-06-09T12:00:00Z",
} as api.FiscalCartaItem;

const CARTA_RESPONSE = {
  cliente_id: "c1",
  cliente_nome: "Acme Ltda",
  versao: "v4",
  risco_total: 99999.99,
  total_fornecedores: 7,
  payload_hash: "1111222233334444555566667777",
  markdown: "# Carta",
  pdf_base64: null,
} as api.FiscalCartaResponse;

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <CartasFiscaisPage />
    </QueryClientProvider>,
  );
}

describe("CartasFiscaisPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renderiza o hero e os controles sem cliente selecionado", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);

    renderPage();

    expect(screen.getByText("Cartas de constatação")).toBeInTheDocument();
    expect(screen.getByText("Cliente")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /gerar nova carta/i }),
    ).toBeInTheDocument();
    // Sem cliente selecionado, não busca cartas nem mostra histórico.
    expect(api.fiscalListarCartas).not.toHaveBeenCalled();
    expect(screen.queryByText("Histórico de Versões")).not.toBeInTheDocument();
  });

  it("carrega clientes ao montar (useQuery)", async () => {
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);

    renderPage();

    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());
  });

  it("ao selecionar um cliente, busca e exibe o histórico de cartas", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalListarCartas).mockResolvedValue({
      cliente_id: "c1",
      total: 1,
      cartas: [CARTA_ITEM],
    } as api.FiscalCartasResponse);

    renderPage();

    // Abre o Select e escolhe o cliente.
    const trigger = screen.getByRole("combobox");
    await user.click(trigger);
    await user.click(await screen.findByRole("option", { name: "Acme Ltda" }));

    await waitFor(() =>
      expect(api.fiscalListarCartas).toHaveBeenCalledWith("c1"),
    );
    expect(await screen.findByText("Histórico de Versões")).toBeInTheDocument();
    // Linha da carta: versão e fornecedores renderizados.
    expect(screen.getByText("v3")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("não mostra histórico quando o cliente não tem cartas (empty state)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalListarCartas).mockResolvedValue({
      cliente_id: "c1",
      total: 0,
      cartas: [],
    } as api.FiscalCartasResponse);

    renderPage();

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);
    await user.click(await screen.findByRole("option", { name: "Acme Ltda" }));

    await waitFor(() =>
      expect(api.fiscalListarCartas).toHaveBeenCalledWith("c1"),
    );
    expect(screen.queryByText("Histórico de Versões")).not.toBeInTheDocument();
  });

  it("mostra toast de erro se a listagem de cartas falhar (sem quebrar)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalListarCartas).mockRejectedValue(
      new Error("Falha de rede"),
    );

    renderPage();

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);
    await user.click(await screen.findByRole("option", { name: "Acme Ltda" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Falha de rede"),
    );
    // A página continua de pé.
    expect(screen.getByText("Cartas de constatação")).toBeInTheDocument();
    expect(screen.queryByText("Histórico de Versões")).not.toBeInTheDocument();
  });

  it("avisa para selecionar um cliente ao tentar gerar sem seleção", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);

    renderPage();

    await user.click(screen.getByRole("button", { name: /gerar nova carta/i }));

    expect(toast.error).toHaveBeenCalledWith("Selecione um cliente");
    expect(api.fiscalGerarCarta).not.toHaveBeenCalled();
  });

  it("gera uma nova carta e mostra o cartão de sucesso", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalListarCartas).mockResolvedValue({
      cliente_id: "c1",
      total: 0,
      cartas: [],
    } as api.FiscalCartasResponse);
    vi.mocked(api.fiscalGerarCarta).mockResolvedValue(CARTA_RESPONSE);

    renderPage();

    // Seleciona cliente.
    const trigger = screen.getByRole("combobox");
    await user.click(trigger);
    await user.click(await screen.findByRole("option", { name: "Acme Ltda" }));
    await waitFor(() =>
      expect(api.fiscalListarCartas).toHaveBeenCalledWith("c1"),
    );

    // Gera a carta.
    await user.click(screen.getByRole("button", { name: /gerar nova carta/i }));

    await waitFor(() =>
      expect(api.fiscalGerarCarta).toHaveBeenCalledWith("c1"),
    );
    expect(
      await screen.findByText("Carta v4 gerada com sucesso"),
    ).toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith(
      "Carta v4 gerada — 7 fornecedores",
    );
    // Sem pdf_base64, não há botão de baixar PDF.
    expect(
      screen.queryByRole("button", { name: /baixar pdf/i }),
    ).not.toBeInTheDocument();
  });

  it("mostra botão de baixar PDF quando a carta gerada tem pdf_base64", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalListarCartas).mockResolvedValue({
      cliente_id: "c1",
      total: 0,
      cartas: [],
    } as api.FiscalCartasResponse);
    vi.mocked(api.fiscalGerarCarta).mockResolvedValue({
      ...CARTA_RESPONSE,
      pdf_base64: "JVBERi0=",
    } as api.FiscalCartaResponse);

    renderPage();

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);
    await user.click(await screen.findByRole("option", { name: "Acme Ltda" }));
    await waitFor(() =>
      expect(api.fiscalListarCartas).toHaveBeenCalledWith("c1"),
    );

    await user.click(screen.getByRole("button", { name: /gerar nova carta/i }));

    expect(
      await screen.findByRole("button", { name: /baixar pdf/i }),
    ).toBeInTheDocument();
  });

  it("mostra toast de erro se a geração da carta falhar", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listarClientes).mockResolvedValue([CLIENTE]);
    vi.mocked(api.fiscalListarCartas).mockResolvedValue({
      cliente_id: "c1",
      total: 0,
      cartas: [],
    } as api.FiscalCartasResponse);
    vi.mocked(api.fiscalGerarCarta).mockRejectedValue(
      new Error("Erro do servidor"),
    );

    renderPage();

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);
    await user.click(await screen.findByRole("option", { name: "Acme Ltda" }));
    await waitFor(() =>
      expect(api.fiscalListarCartas).toHaveBeenCalledWith("c1"),
    );

    await user.click(screen.getByRole("button", { name: /gerar nova carta/i }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Erro do servidor"),
    );
    expect(
      screen.queryByText(/gerada com sucesso/i),
    ).not.toBeInTheDocument();
  });
});
