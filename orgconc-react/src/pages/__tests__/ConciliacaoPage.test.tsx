import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ConciliacaoPage } from "@/pages/ConciliacaoPage";
import type { Anomalia, ConciliacaoResponse } from "@/lib/api";

// useNavigate é espionado; o restante do react-router-dom (MemoryRouter,
// useLocation) é preservado para que o router state real funcione.
const navigateMock = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return { ...actual, useNavigate: () => navigateMock };
});

function makeAnomalia(over: Partial<Anomalia> = {}): Anomalia {
  return {
    severidade: "alto",
    tipo: "duplicidade",
    titulo: "Lançamento duplicado",
    conta: "001",
    valor: 1234.5,
    detalhe: "Detalhe curto",
    ...over,
  };
}

function makeResultado(over: Partial<ConciliacaoResponse> = {}): ConciliacaoResponse {
  return {
    modo: "simulacao",
    report_id: "rep-abc-123",
    extratos: [
      { arquivo: "extrato.ofx", conta: "001", qtd: 12 },
      { arquivo: "razao.csv", conta: "002", qtd: 8 },
    ],
    anomalias: [makeAnomalia()],
    relatorio_md: "# Relatório\n\nConteúdo do relatório em **markdown**.",
    ...over,
  } as ConciliacaoResponse;
}

// Renderiza a página com um resultado entregue via router state (caminho
// principal usado pelo UploadPage).
function renderComState(resultado: ConciliacaoResponse) {
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: "/conciliacao", state: { resultado } }]}
    >
      <ConciliacaoPage />
    </MemoryRouter>,
  );
}

function renderSemState() {
  return render(
    <MemoryRouter>
      <ConciliacaoPage />
    </MemoryRouter>,
  );
}

describe("ConciliacaoPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
  });

  // --------------------------------------------------------------------------
  // Empty state (sem resultado)
  // --------------------------------------------------------------------------

  it("mostra empty state quando nao ha resultado no router state", () => {
    renderSemState();
    expect(screen.getByText(/nenhuma análise ativa/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /ir para upload/i }),
    ).toBeInTheDocument();
  });

  it("renderiza o cabecalho de analises", () => {
    renderSemState();
    expect(screen.getByText(/ANÁLISES/i)).toBeInTheDocument();
  });

  it("usa subtitle de upload no empty state", () => {
    renderSemState();
    expect(
      screen.getByText(/faça o upload dos extratos para iniciar uma nova análise/i),
    ).toBeInTheDocument();
  });

  it("navega para /upload ao clicar no botao do empty state", async () => {
    const user = userEvent.setup();
    renderSemState();
    await user.click(screen.getByRole("button", { name: /ir para upload/i }));
    expect(navigateMock).toHaveBeenCalledWith("/upload");
  });

  // --------------------------------------------------------------------------
  // Fallback de sessionStorage
  // --------------------------------------------------------------------------

  it("usa fallback do sessionStorage quando nao ha router state", () => {
    const resultado = makeResultado({ report_id: "rep-from-session" });
    sessionStorage.setItem("orgconc.last_resultado", JSON.stringify(resultado));
    renderSemState();
    expect(screen.getByText(/rep-from-session/i)).toBeInTheDocument();
    expect(screen.queryByText(/nenhuma análise ativa/i)).not.toBeInTheDocument();
  });

  it("cai no empty state quando sessionStorage contem JSON invalido", () => {
    sessionStorage.setItem("orgconc.last_resultado", "{ json quebrado");
    renderSemState();
    expect(screen.getByText(/nenhuma análise ativa/i)).toBeInTheDocument();
  });

  it("prioriza o router state sobre o sessionStorage", () => {
    sessionStorage.setItem(
      "orgconc.last_resultado",
      JSON.stringify(makeResultado({ report_id: "rep-from-session" })),
    );
    renderComState(makeResultado({ report_id: "rep-from-state" }));
    expect(screen.getByText(/rep-from-state/i)).toBeInTheDocument();
    expect(screen.queryByText(/rep-from-session/i)).not.toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Cabeçalho de resultado + links de export
  // --------------------------------------------------------------------------

  it("renderiza o report_id e o subtitle de resultado", () => {
    renderComState(makeResultado());
    expect(screen.getByText(/ID: rep-abc-123/i)).toBeInTheDocument();
    expect(
      screen.getByText(/confira as anomalias detectadas e baixe o relatório completo/i),
    ).toBeInTheDocument();
  });

  it("renderiza os tres links de export com href correto", () => {
    renderComState(makeResultado({ report_id: "rid-99" }));
    const html = screen.getByRole("link", { name: /HTML/i });
    const excel = screen.getByRole("link", { name: /Excel/i });
    const pdf = screen.getByRole("link", { name: /PDF/i });
    expect(html).toHaveAttribute("href", "/export/html/rid-99");
    expect(excel).toHaveAttribute("href", "/export/xlsx/rid-99");
    expect(pdf).toHaveAttribute("href", "/export/pdf/rid-99");
    expect(html).toHaveAttribute("target", "_blank");
    expect(html).toHaveAttribute("rel", "noopener noreferrer");
  });

  // --------------------------------------------------------------------------
  // KPI cards
  // --------------------------------------------------------------------------

  it("calcula o total de transacoes somando qtd dos extratos (pt-BR)", () => {
    renderComState(
      makeResultado({
        extratos: [
          { arquivo: "a.ofx", conta: "001", qtd: 1200 },
          { arquivo: "b.csv", conta: "002", qtd: 345 },
        ],
      }),
    );
    expect(screen.getByText("Total Transações")).toBeInTheDocument();
    // 1545 formatado em pt-BR => "1.545"
    expect(screen.getByText("1.545")).toBeInTheDocument();
  });

  it("exibe o total de anomalias e o card Modo com label mapeado", () => {
    renderComState(
      makeResultado({
        modo: "opus",
        anomalias: [makeAnomalia(), makeAnomalia({ titulo: "Outra" })],
      }),
    );
    expect(screen.getByText("Total Anomalias")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    // MODO_LABEL.opus === "Opus"
    expect(screen.getByText("Opus")).toBeInTheDocument();
  });

  it("usa o proprio modo como display quando nao ha label mapeado", () => {
    renderComState(makeResultado({ modo: "modo_desconhecido", anomalias: [] }));
    expect(screen.getByText("modo_desconhecido")).toBeInTheDocument();
  });

  it("mostra 0 anomalias quando a lista esta vazia", () => {
    renderComState(makeResultado({ anomalias: [] }));
    // O KPI de Total Anomalias deve exibir 0
    const card = screen.getByText("Total Anomalias").closest("div")
      ?.parentElement as HTMLElement;
    expect(within(card).getByText("0")).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Tabela de anomalias
  // --------------------------------------------------------------------------

  it("mostra mensagem de ausencia quando nao ha anomalias", () => {
    renderComState(makeResultado({ anomalias: [] }));
    expect(screen.getByText(/nenhuma anomalia detectada/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renderiza os cabecalhos da tabela de anomalias", () => {
    renderComState(makeResultado());
    expect(screen.getByRole("columnheader", { name: "Severidade" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Tipo" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Título" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Conta" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Valor/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Detalhe" })).toBeInTheDocument();
  });

  it("renderiza os dados de uma anomalia incluindo valor formatado pt-BR", () => {
    renderComState(
      makeResultado({
        anomalias: [
          makeAnomalia({
            severidade: "crítico",
            tipo: "smurfing",
            titulo: "Fracionamento suspeito",
            conta: "123",
            valor: 1234.5,
            detalhe: "Detalhe legível",
          }),
        ],
      }),
    );
    expect(screen.getByText("crítico")).toBeInTheDocument();
    expect(screen.getByText("smurfing")).toBeInTheDocument();
    expect(screen.getByText("Fracionamento suspeito")).toBeInTheDocument();
    expect(screen.getByText("123")).toBeInTheDocument();
    // 1234.5 com minimumFractionDigits: 2 => "1.234,50"
    expect(screen.getByText("1.234,50")).toBeInTheDocument();
    expect(screen.getByText("Detalhe legível")).toBeInTheDocument();
  });

  it("exibe travessao quando valor da anomalia e nulo", () => {
    renderComState(
      makeResultado({
        anomalias: [
          makeAnomalia({ valor: null as unknown as number, detalhe: "x" }),
        ],
      }),
    );
    const rows = screen.getAllByRole("row");
    // linha de cabecalho + 1 de dados
    const dataRow = rows[1];
    expect(within(dataRow).getByText("—")).toBeInTheDocument();
  });

  it("exibe travessao no detalhe quando ausente", () => {
    renderComState(
      makeResultado({
        anomalias: [
          makeAnomalia({ valor: 10, detalhe: null as unknown as string }),
        ],
      }),
    );
    // valor formatado "10,00" presente; o detalhe vazio vira "—"
    expect(screen.getByText("10,00")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("trunca detalhe longo a 80 caracteres com reticencias e title completo", () => {
    const longo = "A".repeat(120);
    renderComState(
      makeResultado({ anomalias: [makeAnomalia({ detalhe: longo })] }),
    );
    const cell = screen.getByText(/A{80}…/);
    expect(cell).toBeInTheDocument();
    // title preserva o detalhe completo (tooltip)
    expect(cell).toHaveAttribute("title", longo);
  });

  it("usa estilo info quando severidade e desconhecida", () => {
    renderComState(
      makeResultado({
        anomalias: [makeAnomalia({ severidade: "inexistente" })],
      }),
    );
    expect(screen.getByText("inexistente")).toBeInTheDocument();
  });

  it("limita a exibicao a 50 anomalias e mostra o aviso de total", () => {
    const muitas = Array.from({ length: 73 }, (_, i) =>
      makeAnomalia({ titulo: `Anomalia ${i}`, conta: `c${i}` }),
    );
    renderComState(makeResultado({ anomalias: muitas }));
    // 50 linhas de dados + 1 cabecalho = 51 linhas
    expect(screen.getAllByRole("row")).toHaveLength(51);
    expect(
      screen.getByText(/Exibindo 50 de 73 anomalias/i),
    ).toBeInTheDocument();
  });

  it("nao mostra aviso de total quando ha 50 ou menos anomalias", () => {
    const cinquenta = Array.from({ length: 50 }, (_, i) =>
      makeAnomalia({ titulo: `A${i}`, conta: `c${i}` }),
    );
    renderComState(makeResultado({ anomalias: cinquenta }));
    expect(screen.queryByText(/Exibindo 50 de/i)).not.toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Toggle de relatório (expandir/recolher)
  // --------------------------------------------------------------------------

  it("renderiza o relatorio markdown e alterna entre expandir e recolher", async () => {
    const user = userEvent.setup();
    renderComState(
      makeResultado({ relatorio_md: "# Título do laudo\n\nParágrafo." }),
    );
    // markdown convertido em heading
    expect(
      screen.getByRole("heading", { name: /Título do laudo/i }),
    ).toBeInTheDocument();

    // estado inicial: recolhido => botao "Expandir relatório"
    const btnExpandir = screen.getByRole("button", {
      name: /expandir relatório/i,
    });
    expect(btnExpandir).toBeInTheDocument();

    await user.click(btnExpandir);
    // apos expandir => botao "Recolher"
    expect(
      screen.getByRole("button", { name: /recolher/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /expandir relatório/i }),
    ).not.toBeInTheDocument();

    // recolher de volta
    await user.click(screen.getByRole("button", { name: /recolher/i }));
    expect(
      screen.getByRole("button", { name: /expandir relatório/i }),
    ).toBeInTheDocument();
  });

  it("renderiza a label Relatório acima do toggle", () => {
    // markdown sem a palavra "Relatório" para isolar a label da pagina
    renderComState(makeResultado({ relatorio_md: "Apenas texto simples." }));
    const label = screen.getByText("Relatório");
    expect(label).toBeInTheDocument();
    expect(label.tagName).toBe("SPAN");
  });
});
