import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AuditoriaForensePage } from "@/pages/AuditoriaForensePage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    fiscalLaudoResumo: vi.fn(),
    fiscalLaudoBlob: vi.fn(),
  };
});

// toast (sonner) não precisa de provider; mockamos para inspecionar os caminhos
// de validação/erro sem depender da renderização do toaster.
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

import * as api from "@/lib/api";
import { toast } from "sonner";

const CLIENTE = {
  id: "c1",
  nome: "Acme Ltda",
  cnpj: "11222333000181",
  plano: "pro",
  ativo: true,
} as api.Cliente;

const RESUMO = {
  empresa: {
    cnpj: "11.222.333/0001-81",
    razao_social: "Acme Auditada SA",
    porte: "DEMAIS",
    situacao: "ATIVA",
    cnae: "6201500",
  },
  conta: "158083",
  periodo: { inicio: "2024-01-01", fim: "2024-06-30" },
  enriquecimento_pendente: 0,
  regime: {
    volume_bruto: 8_000_000,
    volume_anualizado: 16_000_000,
    teto: 4_800_000,
    multiplo_do_teto: 3.3,
    classe: "ALTO",
    incompativel: true,
  },
  n_transacoes: 1234,
  meses_observados: 6,
  heatmap: {
    CRITICO: { qtd: 10, volume: 5_000_000 },
    ALTO: { qtd: 20, volume: 2_000_000 },
    MEDIO: { qtd: 30, volume: 800_000 },
    BAIXO: { qtd: 40, volume: 200_000 },
  },
  retencao_estimada: 120_000,
  sinais: { pos_baixa: 3, smurfing: 7, carrossel: 2 },
  top_disposicoes: [
    {
      data: "2024-03-15T00:00:00",
      valor: 99_000,
      cnpj: "00.000.000/0001-00",
      meio: "PIX",
      categoria_tributaria: "SERVICO",
      risk_score: 87,
      risco_classe: "CRITICO",
      sinais: ["pos_baixa", "smurfing"],
    },
  ],
} as api.FiscalAuditoriaResumo;

function ofxFile(name = "extrato.ofx", size = 1024): File {
  const file = new File(["<OFX></OFX>"], name, { type: "application/x-ofx" });
  // jsdom não calcula size a partir do conteúdo de forma confiável; força.
  Object.defineProperty(file, "size", { value: size });
  return file;
}

function fileInput(): HTMLInputElement {
  // O <input type="file"> está oculto (className="hidden"), sem role/label próprio.
  const el = document.querySelector('input[type="file"]') as HTMLInputElement;
  return el;
}

function cnpjInput(): HTMLInputElement {
  return screen.getByPlaceholderText("00.000.000/0000-00") as HTMLInputElement;
}

describe("AuditoriaForensePage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    // Padrão silencioso: a maioria dos testes não depende de clientes.
    vi.mocked(api.listarClientes).mockResolvedValue([]);
  });

  it("carrega clientes ao montar e renderiza o cabecalho", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    render(<AuditoriaForensePage />);

    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));
    expect(screen.getByText("Regime ×")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /analisar regime × teto/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /baixar laudo xlsx/i }),
    ).toBeInTheDocument();
  });

  it("mostra toast de erro se a carga de clientes falhar (sem quebrar)", async () => {
    vi.mocked(api.listarClientes).mockRejectedValueOnce(new Error("boom"));
    render(<AuditoriaForensePage />);

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Falha ao carregar clientes"),
    );
    // A página continua renderizada mesmo com a falha.
    expect(screen.getByText("Regime ×")).toBeInTheDocument();
  });

  it("nao renderiza o resumo antes de analisar (empty state)", async () => {
    render(<AuditoriaForensePage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    expect(
      screen.queryByText("Múltiplo do Teto (achado central)"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Heatmap de Risco por Transação"),
    ).not.toBeInTheDocument();
  });

  it("bloqueia analise quando o CNPJ nao tem 14 digitos", async () => {
    render(<AuditoriaForensePage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    fireEvent.click(
      screen.getByRole("button", { name: /analisar regime × teto/i }),
    );

    expect(toast.error).toHaveBeenCalledWith(
      "Informe o CNPJ da empresa auditada (14 dígitos).",
    );
    expect(api.fiscalLaudoResumo).not.toHaveBeenCalled();
  });

  it("bloqueia analise quando ha CNPJ valido mas nenhum OFX", async () => {
    render(<AuditoriaForensePage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    fireEvent.change(cnpjInput(), { target: { value: "11.222.333/0001-81" } });
    fireEvent.click(
      screen.getByRole("button", { name: /analisar regime × teto/i }),
    );

    expect(toast.error).toHaveBeenCalledWith("Envie ao menos 1 extrato OFX.");
    expect(api.fiscalLaudoResumo).not.toHaveBeenCalled();
  });

  it("rejeita arquivos que nao sao .ofx e aceita os .ofx", async () => {
    render(<AuditoriaForensePage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    const pdf = new File(["x"], "naoaceito.pdf", { type: "application/pdf" });
    Object.defineProperty(pdf, "size", { value: 10 });
    fireEvent.change(fileInput(), {
      target: { files: [ofxFile("extrato.ofx", 2048), pdf] },
    });

    expect(toast.warning).toHaveBeenCalledWith(
      "Apenas arquivos .ofx são aceitos aqui.",
    );
    // Apenas o .ofx aparece na lista.
    expect(screen.getByText("extrato.ofx")).toBeInTheDocument();
    expect(screen.queryByText("naoaceito.pdf")).not.toBeInTheDocument();
  });

  it("analisa e renderiza o resumo retornado pela API", async () => {
    vi.mocked(api.fiscalLaudoResumo).mockResolvedValueOnce(RESUMO);
    render(<AuditoriaForensePage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    fireEvent.change(cnpjInput(), { target: { value: "11.222.333/0001-81" } });
    fireEvent.change(fileInput(), { target: { files: [ofxFile()] } });

    fireEvent.click(
      screen.getByRole("button", { name: /analisar regime × teto/i }),
    );

    await waitFor(() => expect(api.fiscalLaudoResumo).toHaveBeenCalledTimes(1));
    // CNPJ enviado só com dígitos; conta trimada.
    expect(api.fiscalLaudoResumo).toHaveBeenCalledWith(
      "11222333000181",
      "",
      expect.arrayContaining([expect.any(File)]),
    );

    // Renderiza identificação + achado central + sinais.
    await waitFor(() =>
      expect(screen.getByText("Acme Auditada SA")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Múltiplo do Teto (achado central)"),
    ).toBeInTheDocument();
    // "ALTO" aparece no badge de regime e na linha do heatmap; basta existir.
    expect(screen.getAllByText("ALTO").length).toBeGreaterThanOrEqual(1);
    // Múltiplo do teto renderizado (3,3× no formato pt-BR).
    expect(screen.getByText(/3,3/)).toBeInTheDocument();
    expect(
      screen.getByText("Heatmap de Risco por Transação"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Top Disposições por Risk Score"),
    ).toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith(
      "1234 transações analisadas · regime ALTO",
    );
  });

  it("mostra toast de erro se a analise forense falhar (sem quebrar)", async () => {
    vi.mocked(api.fiscalLaudoResumo).mockRejectedValueOnce(
      new Error("erro do servidor"),
    );
    render(<AuditoriaForensePage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    fireEvent.change(cnpjInput(), { target: { value: "11.222.333/0001-81" } });
    fireEvent.change(fileInput(), { target: { files: [ofxFile()] } });
    fireEvent.click(
      screen.getByRole("button", { name: /analisar regime × teto/i }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("erro do servidor"),
    );
    // Sem resumo renderizado.
    expect(
      screen.queryByText("Múltiplo do Teto (achado central)"),
    ).not.toBeInTheDocument();
  });

  it("baixa o laudo XLSX disparando o blob da API", async () => {
    const blob = new Blob(["xlsx"], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    vi.mocked(api.fiscalLaudoBlob).mockResolvedValueOnce({
      blob,
      filename: "laudo-acme.xlsx",
    });

    // jsdom não implementa URL.createObjectURL / a.click(); stub.
    const createObjectURL = vi.fn(() => "blob:fake");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    render(<AuditoriaForensePage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    fireEvent.change(cnpjInput(), { target: { value: "11.222.333/0001-81" } });
    fireEvent.change(fileInput(), { target: { files: [ofxFile()] } });
    fireEvent.click(
      screen.getByRole("button", { name: /baixar laudo xlsx/i }),
    );

    await waitFor(() => expect(api.fiscalLaudoBlob).toHaveBeenCalledTimes(1));
    expect(api.fiscalLaudoBlob).toHaveBeenCalledWith(
      "11222333000181",
      "",
      expect.arrayContaining([expect.any(File)]),
    );
    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("Laudo XLSX (11 abas) gerado."),
    );

    clickSpy.mockRestore();
    vi.unstubAllGlobals();
  });

  it("mostra toast de erro se a geracao do laudo falhar", async () => {
    vi.mocked(api.fiscalLaudoBlob).mockRejectedValueOnce(
      new Error("falha no xlsx"),
    );
    render(<AuditoriaForensePage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    fireEvent.change(cnpjInput(), { target: { value: "11.222.333/0001-81" } });
    fireEvent.change(fileInput(), { target: { files: [ofxFile()] } });
    fireEvent.click(
      screen.getByRole("button", { name: /baixar laudo xlsx/i }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("falha no xlsx"),
    );
  });
});
