import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { RelatoriosPage } from "@/pages/RelatoriosPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarConciliacoes: vi.fn(),
    carregarHistoricoLocal: vi.fn(),
  };
});

import * as api from "@/lib/api";

// recharts' ResponsiveContainer depende de ResizeObserver, ausente no jsdom.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;

const CONCILIACAO: api.ConciliacaoMeta = {
  report_id: "abcdef0123456789-relatorio",
  modo: "haiku",
  total_transacoes: 120,
  total_anomalias: 4,
  criado_em: "2026-06-01T10:00:00Z",
  exports: {
    html: "/export/html/abcdef0123456789",
    xlsx: "/export/xlsx/abcdef0123456789",
    pdf: "/export/pdf/abcdef0123456789",
  },
};

function renderPage() {
  return render(
    <MemoryRouter>
      <RelatoriosPage />
    </MemoryRouter>,
  );
}

describe("RelatoriosPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    // Por padrão, sem histórico local; cada teste configura listarConciliacoes.
    vi.mocked(api.carregarHistoricoLocal).mockReturnValue([]);
  });

  it("dispara listarConciliacoes ao montar e exibe o cabecalho", async () => {
    vi.mocked(api.listarConciliacoes).mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(api.listarConciliacoes).toHaveBeenCalledTimes(1));
    expect(screen.getByText("03 · RELATÓRIOS")).toBeInTheDocument();
  });

  it("renderiza as conciliacoes retornadas pela API na tabela", async () => {
    vi.mocked(api.listarConciliacoes).mockResolvedValue([CONCILIACAO]);
    renderPage();

    // Report ID truncado em 12 chars + reticências.
    await waitFor(() =>
      expect(screen.getByText("abcdef012345…")).toBeInTheDocument(),
    );
    // Badge do modo usa o rótulo de MODO_LABEL ("haiku" -> "Haiku").
    expect(screen.getByText("Haiku")).toBeInTheDocument();
    // Total de transações e anomalias na célula da linha (cell, não o KPI).
    const cells = screen.getAllByRole("cell");
    expect(cells.some((c) => c.textContent === "120")).toBe(true);
    expect(cells.some((c) => c.textContent === "4")).toBe(true);
    // Cabeçalhos da tabela.
    expect(screen.getByText("Report ID")).toBeInTheDocument();
    expect(screen.getByText("Exports")).toBeInTheDocument();
    // Links de export com target _blank.
    expect(screen.getByRole("link", { name: /HTML/i })).toHaveAttribute(
      "href",
      "/export/html/abcdef0123456789",
    );
    expect(screen.getByRole("link", { name: /PDF/i })).toHaveAttribute("target", "_blank");
  });

  it("calcula os KPIs a partir das linhas", async () => {
    vi.mocked(api.listarConciliacoes).mockResolvedValue([CONCILIACAO]);
    renderPage();

    await waitFor(() => expect(screen.getByText("Conciliações")).toBeInTheDocument());
    // KPIs: 1 conciliação, 120 transações, 4 anomalias, taxa = 4/120*100 = 3.3%.
    expect(screen.getByText("Transações")).toBeInTheDocument();
    expect(screen.getByText("Anomalias")).toBeInTheDocument();
    expect(screen.getByText("Taxa anomalias")).toBeInTheDocument();
    expect(screen.getByText("3.3%")).toBeInTheDocument();
  });

  it("mostra empty state e botao de primeira conciliacao quando nao ha dados", async () => {
    vi.mocked(api.listarConciliacoes).mockResolvedValue([]);
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Nenhuma conciliação realizada ainda.")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /fazer primeira conciliação/i }),
    ).toBeInTheDocument();
  });

  it("usa o historico local quando a API retorna vazio", async () => {
    vi.mocked(api.listarConciliacoes).mockResolvedValue([]);
    vi.mocked(api.carregarHistoricoLocal).mockReturnValue([
      {
        id: "local-report-id-987654",
        modo: "simulacao_local",
        ts: "2026-05-20T09:00:00Z",
        total_tx: 50,
        total_anom: 2,
      },
    ]);
    renderPage();

    // Linha do histórico local renderiza (ID truncado em 12 chars).
    await waitFor(() =>
      expect(screen.getByText("local-report…")).toBeInTheDocument(),
    );
    // Rótulo do modo local.
    expect(screen.getByText("Simulação")).toBeInTheDocument();
  });

  it("nao quebra quando listarConciliacoes rejeita (cai para historico local vazio)", async () => {
    vi.mocked(api.listarConciliacoes).mockRejectedValue(new Error("500"));
    renderPage();

    // Após a falha, mostra o empty state sem lançar erro.
    await waitFor(() =>
      expect(screen.getByText("Nenhuma conciliação realizada ainda.")).toBeInTheDocument(),
    );
    expect(api.listarConciliacoes).toHaveBeenCalledTimes(1);
  });

  it("filtra a tabela pela busca por ID/modo", async () => {
    const user = userEvent.setup();
    const outra: api.ConciliacaoMeta = {
      ...CONCILIACAO,
      report_id: "zzzz999888777-outra",
      modo: "opus",
      exports: {
        html: "/export/html/zzzz999888777",
        xlsx: "/export/xlsx/zzzz999888777",
        pdf: "/export/pdf/zzzz999888777",
      },
    };
    vi.mocked(api.listarConciliacoes).mockResolvedValue([CONCILIACAO, outra]);
    renderPage();

    await waitFor(() => expect(screen.getByText("abcdef012345…")).toBeInTheDocument());
    expect(screen.getByText("zzzz99988877…")).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Buscar por ID ou modo…");
    await user.type(input, "abcdef");

    // A linha que não corresponde some; a correspondente permanece.
    await waitFor(() =>
      expect(screen.queryByText("zzzz99988877…")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("abcdef012345…")).toBeInTheDocument();
  });

  it("copia o report id para a area de transferencia ao clicar no botao", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    vi.mocked(api.listarConciliacoes).mockResolvedValue([CONCILIACAO]);
    renderPage();

    const btn = await screen.findByRole("button", { name: /copiar report id/i });
    await user.click(btn);

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("abcdef0123456789-relatorio"),
    );
  });
});
