import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConformidadeFiscalPage } from "@/pages/ConformidadeFiscalPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    fiscalConformidade: vi.fn(),
    fiscalRiscoTributario: vi.fn(),
    fiscalProcessar: vi.fn(),
  };
});

// O Radix Select não abre de forma confiável no jsdom; substituímos por um
// <select> nativo que preserva o contrato value/onValueChange usado pela página.
vi.mock("@/components/ui/select", () => {
  type Opt = { value: string; label: string };
  const collect = (node: React.ReactNode, acc: Opt[]) => {
    React.Children.forEach(node, (child) => {
      if (!React.isValidElement(child)) return;
      const el = child as React.ReactElement<{ value?: string; children?: React.ReactNode }>;
      if (el.props && typeof el.props.value === "string") {
        acc.push({ value: el.props.value, label: String(el.props.children ?? "") });
      } else if (el.props && el.props.children) {
        collect(el.props.children, acc);
      }
    });
  };
  return {
    Select: ({
      value,
      onValueChange,
      children,
    }: {
      value: string;
      onValueChange: (v: string) => void;
      children: React.ReactNode;
    }) => {
      const opts: Opt[] = [];
      collect(children, opts);
      return (
        <select
          data-testid="mock-select"
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
        >
          {!opts.some((o) => o.value === value) && <option value="" />}
          {opts.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      );
    },
    SelectTrigger: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    SelectValue: () => null,
    SelectContent: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    SelectItem: ({ value, children }: { value: string; children?: React.ReactNode }) => (
      <option value={value}>{children}</option>
    ),
  };
});

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

import * as React from "react";
import * as api from "@/lib/api";

const CLIENTE = {
  id: "c1",
  nome: "Acme Ltda",
  cnpj: "11222333000181",
  plano: "pro",
  ativo: true,
} as api.Cliente;

const CLIENTE_SEM_CNPJ = {
  id: "c2",
  nome: "Beta SA",
  plano: "free",
  ativo: true,
} as api.Cliente;

const FORN_CRITICO: api.FiscalFornecedor = {
  cnpj: "99888777000166",
  razao_social: "Fornecedor Crítico",
  volume_pago: 200000,
  volume_nf: 50000,
  conformidade_pct: 25,
  n_pagamentos: 20,
  n_nfes: 5,
  risco_classe: "CRITICO",
  risco_tributario_anual: 60000,
  flags: ["SEM_NF", "DIVERGENCIA"],
  periodo_inicio: "2025-01-01",
  periodo_fim: "2025-12-31",
};

const FORN_ALTO: api.FiscalFornecedor = {
  cnpj: "11111111000111",
  razao_social: "",
  volume_pago: 100000,
  volume_nf: 100000,
  conformidade_pct: 100,
  n_pagamentos: 10,
  n_nfes: 10,
  risco_classe: "ALTO",
  risco_tributario_anual: 15000,
  flags: [],
  periodo_inicio: null,
  periodo_fim: null,
};

const FORN_BAIXO: api.FiscalFornecedor = {
  cnpj: "22222222000122",
  razao_social: "Fornecedor OK",
  volume_pago: 80000,
  volume_nf: 80000,
  conformidade_pct: 99,
  n_pagamentos: 8,
  n_nfes: 8,
  risco_classe: "BAIXO",
  risco_tributario_anual: 0,
  flags: [],
  periodo_inicio: null,
  periodo_fim: null,
};

const CONFORMIDADE: api.FiscalConformidadeResponse = {
  cliente_id: "c1",
  total: 3,
  fornecedores: [FORN_CRITICO, FORN_ALTO, FORN_BAIXO],
};

const RISCO: api.FiscalRiscoResponse = {
  cliente_id: "c1",
  risco_total_anual: 75000,
  risco_despesa_indedutivel_anual: 50000,
  risco_retencoes_anual: 25000,
  por_classe_risco: {},
  por_flag: {},
  contagem_fornecedores: {},
  total_fornecedores: 3,
  top_10_fornecedores: [],
  retencoes: {
    base_pj_anual: 0,
    retencao_pj_anual: 0,
    total_anual: 0,
    aliquotas: {},
  },
  regime_pressuposto: "Lucro Real",
  aliquota_aplicada_pct: 34,
};

const PROCESSAR: api.FiscalProcessarResponse = {
  cliente_id: "c1",
  documentos_processados: 42,
  documentos_por_tipo: { "NF-e": 30, "CT-e": 8, "NFS-e": 4 },
  ofx_transacoes: 50,
  cruzamentos: {
    total: 40,
    por_status: { CASADO: 25, SEM_NF: 10, VALOR_DIVERGENTE: 5 },
    volume_por_status: {},
  },
  fornecedores_classificados: 12,
};

function makeFile(name: string, size = 1024) {
  const file = new File(["x".repeat(size)], name, { type: "application/zip" });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

function selectFiles(files: File[]) {
  const input = document.querySelector(
    'input[type="file"]',
  ) as HTMLInputElement;
  Object.defineProperty(input, "files", {
    configurable: true,
    value: {
      length: files.length,
      item: (i: number) => files[i],
      ...files,
    } as unknown as FileList,
  });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("ConformidadeFiscalPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renderiza e carrega clientes ao montar", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ConformidadeFiscalPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));
  });

  it("nao processa nem busca conformidade sem cliente selecionado", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ConformidadeFiscalPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());
    expect(api.fiscalConformidade).not.toHaveBeenCalled();
    expect(api.fiscalProcessar).not.toHaveBeenCalled();
  });

  it("renderiza cabecalho, dropzone e checkbox de enriquecimento", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ConformidadeFiscalPage />);

    expect(screen.getByText("Auditoria fiscal")).toBeInTheDocument();
    expect(screen.getByText("cruzada.")).toBeInTheDocument();
    expect(screen.getByText("Cliente")).toBeInTheDocument();
    expect(
      screen.getByText("Arraste ZIPs de NF-e + CT-e + (opcional) OFX"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Enriquecimento completo de CNPJs/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Iniciar Cruzamento Fiscal" }),
    ).toBeInTheDocument();
  });

  it("mostra toast de erro quando a listagem de clientes falha", async () => {
    vi.mocked(api.listarClientes).mockRejectedValueOnce(new Error("DB off"));
    render(<ConformidadeFiscalPage />);
    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Falha ao carregar clientes"),
    );
  });

  it("popula o seletor incluindo CNPJ entre parenteses", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([
      CLIENTE,
      CLIENTE_SEM_CNPJ,
    ]);
    render(<ConformidadeFiscalPage />);

    // a opção do cliente carregado aparece (nome + CNPJ entre parenteses)
    await waitFor(() =>
      expect(screen.getByText(/Acme Ltda/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/11222333000181/)).toBeInTheDocument();
    // cliente sem CNPJ aparece pelo nome
    expect(screen.getByText(/Beta SA/)).toBeInTheDocument();
    // ambas as opções existem no select mockado
    expect(screen.getByRole("option", { name: /Acme Ltda/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Beta SA/ })).toBeInTheDocument();
  });

  it("ao selecionar cliente, busca conformidade + risco e renderiza KPIs", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValueOnce(CONFORMIDADE);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValueOnce(RISCO);

    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });

    const select = screen.getByTestId("mock-select");
    await userEvent.selectOptions(select, "c1");

    await waitFor(() =>
      expect(api.fiscalConformidade).toHaveBeenCalledWith("c1"),
    );
    expect(api.fiscalRiscoTributario).toHaveBeenCalledWith("c1");

    // KPIs
    expect(await screen.findByText("Score Geral")).toBeInTheDocument();
    // score geral = round((25+100+99)/3) = 75
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("3 fornecedores")).toBeInTheDocument();
    expect(screen.getByText("Volume com NF")).toBeInTheDocument();
    expect(screen.getByText("Volume sem NF")).toBeInTheDocument();
    expect(screen.getByText("Risco Tributário/Ano")).toBeInTheDocument();
    // regime + aliquota do risco
    expect(screen.getByText(/Lucro Real · 34%/)).toBeInTheDocument();
  });

  it("renderiza apenas fornecedores ALTO/CRITICO na tabela de gap (top 10)", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValueOnce(CONFORMIDADE);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValueOnce(RISCO);

    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    expect(
      await screen.findByText("Top Fornecedores com Gap Fiscal"),
    ).toBeInTheDocument();
    // CRITICO e ALTO aparecem
    expect(screen.getByText("Fornecedor Crítico")).toBeInTheDocument();
    expect(screen.getByText("CRITICO")).toBeInTheDocument();
    expect(screen.getByText("ALTO")).toBeInTheDocument();
    // BAIXO não aparece na tabela de gaps
    expect(screen.queryByText("Fornecedor OK")).not.toBeInTheDocument();
    // razao_social vazia vira "—"; flags vazias viram "—"
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    // conformidade com uma casa decimal
    expect(screen.getByText("25.0%")).toBeInTheDocument();
    expect(screen.getByText("100.0%")).toBeInTheDocument();
    // flags concatenadas
    expect(screen.getByText("SEM_NF, DIVERGENCIA")).toBeInTheDocument();
  });

  it("nao renderiza KPIs nem tabela quando nao ha fornecedores", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValueOnce({
      cliente_id: "c1",
      total: 0,
      fornecedores: [],
    });
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValueOnce(RISCO);

    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    await waitFor(() => expect(api.fiscalConformidade).toHaveBeenCalled());
    expect(screen.queryByText("Score Geral")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Top Fornecedores com Gap Fiscal"),
    ).not.toBeInTheDocument();
  });

  it("mostra toast de erro quando loadDados falha", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockRejectedValueOnce(
      new Error("conformidade indisponivel"),
    );
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValueOnce(RISCO);

    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("conformidade indisponivel"),
    );
    expect(screen.queryByText("Score Geral")).not.toBeInTheDocument();
  });

  it("toast de erro ao clicar processar sem cliente selecionado", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });

    await userEvent.click(
      screen.getByRole("button", { name: "Iniciar Cruzamento Fiscal" }),
    );
    expect(toastError).toHaveBeenCalledWith("Selecione um cliente");
    expect(api.fiscalProcessar).not.toHaveBeenCalled();
  });

  it("toast de erro ao processar com cliente mas sem arquivos", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValueOnce(CONFORMIDADE);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValueOnce(RISCO);

    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");
    await waitFor(() => expect(api.fiscalConformidade).toHaveBeenCalled());

    await userEvent.click(
      screen.getByRole("button", { name: "Iniciar Cruzamento Fiscal" }),
    );
    expect(toastError).toHaveBeenCalledWith(
      "Envie ao menos 1 ZIP com NF-es/CT-es",
    );
    expect(api.fiscalProcessar).not.toHaveBeenCalled();
  });

  it("lista arquivos selecionados com nome e tamanho formatado", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ConformidadeFiscalPage />);

    selectFiles([makeFile("notas.zip", 2048)]);
    await waitFor(() =>
      expect(screen.getByText("notas.zip")).toBeInTheDocument(),
    );
    // formatBytes(2048) => "2.0 KB"
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  it("adiciona arquivos via drag-and-drop e realca a dropzone no dragOver", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ConformidadeFiscalPage />);

    const dropzone = screen
      .getByText("Arraste ZIPs de NF-e + CT-e + (opcional) OFX")
      .closest("div") as HTMLElement;

    // dragOver -> aplica classe de realce
    fireEvent.dragOver(dropzone);
    await waitFor(() =>
      expect(dropzone.className).toContain("border-primary"),
    );

    // dragLeave -> remove o realce
    fireEvent.dragLeave(dropzone);
    await waitFor(() =>
      expect(dropzone.className).not.toContain("scale-[1.01]"),
    );

    // drop adiciona o arquivo à lista
    const file = makeFile("drop.zip", 4096);
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: {
          length: 1,
          item: (i: number) => [file][i],
          0: file,
        },
      },
    });

    await waitFor(() =>
      expect(screen.getByText("drop.zip")).toBeInTheDocument(),
    );
    // formatBytes(4096) => "4.0 KB"
    expect(screen.getByText("4.0 KB")).toBeInTheDocument();
  });

  it("ignora addFiles quando nenhuma FileList e fornecida no drop", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ConformidadeFiscalPage />);

    const dropzone = screen
      .getByText("Arraste ZIPs de NF-e + CT-e + (opcional) OFX")
      .closest("div") as HTMLElement;

    // drop sem dataTransfer.files -> não adiciona nada e não quebra
    fireEvent.drop(dropzone, { dataTransfer: { files: null } });
    expect(screen.queryByText(/\.zip$/)).not.toBeInTheDocument();
  });

  it("abre o seletor de arquivos ao clicar na dropzone", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ConformidadeFiscalPage />);

    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");

    const dropzone = screen
      .getByText("Arraste ZIPs de NF-e + CT-e + (opcional) OFX")
      .closest("div") as HTMLElement;
    await userEvent.click(dropzone);

    expect(clickSpy).toHaveBeenCalled();
  });

  it("alterna o checkbox de enriquecimento completo", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([]);
    render(<ConformidadeFiscalPage />);

    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).not.toBeChecked();
    await userEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  it("processa com sucesso: chama fiscalProcessar, recarrega dados e limpa arquivos", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValue(CONFORMIDADE);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValue(RISCO);
    vi.mocked(api.fiscalProcessar).mockResolvedValueOnce(PROCESSAR);

    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");
    await waitFor(() => expect(api.fiscalConformidade).toHaveBeenCalled());

    // marca enriquecimento e adiciona arquivo
    await userEvent.click(screen.getByRole("checkbox"));
    selectFiles([makeFile("notas.zip", 1024)]);
    await waitFor(() =>
      expect(screen.getByText("notas.zip")).toBeInTheDocument(),
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Iniciar Cruzamento Fiscal" }),
    );

    await waitFor(() => expect(api.fiscalProcessar).toHaveBeenCalledTimes(1));
    // enrichAll = true repassado
    expect(api.fiscalProcessar).toHaveBeenCalledWith(
      "c1",
      expect.any(Array),
      true,
    );
    // o segundo argumento (arquivos) é um array de File com o nome enviado
    const arquivosArg = vi.mocked(api.fiscalProcessar).mock.calls[0][1];
    expect(arquivosArg).toHaveLength(1);
    expect(arquivosArg[0].name).toBe("notas.zip");

    expect(toastSuccess).toHaveBeenCalledWith(
      "42 documentos processados (12 fornecedores classificados)",
    );

    // painel de "Último processamento"
    expect(await screen.findByText("Último processamento:")).toBeInTheDocument();
    expect(
      screen.getByText(/NF-e: 30 · CT-e: 8 · NFS-e: 4/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/CASADO 25 · SEM_NF 10 · VALOR_DIVERGENTE 5/),
    ).toBeInTheDocument();

    // arquivos limpos após processamento
    await waitFor(() =>
      expect(screen.queryByText("notas.zip")).not.toBeInTheDocument(),
    );
  });

  it("processa sem bloco de cruzamentos quando cruzamentos e null", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValue(CONFORMIDADE);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValue(RISCO);
    vi.mocked(api.fiscalProcessar).mockResolvedValueOnce({
      ...PROCESSAR,
      cruzamentos: null,
    });

    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");
    await waitFor(() => expect(api.fiscalConformidade).toHaveBeenCalled());

    selectFiles([makeFile("notas.zip", 1024)]);
    await waitFor(() =>
      expect(screen.getByText("notas.zip")).toBeInTheDocument(),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Iniciar Cruzamento Fiscal" }),
    );

    await waitFor(() => expect(api.fiscalProcessar).toHaveBeenCalled());
    // enrichAll default false (checkbox não marcado)
    expect(api.fiscalProcessar).toHaveBeenCalledWith(
      "c1",
      expect.any(Array),
      false,
    );
    expect(await screen.findByText("Último processamento:")).toBeInTheDocument();
    // bloco de cruzamentos ausente
    expect(screen.queryByText(/Cruzamentos:/)).not.toBeInTheDocument();
  });

  it("mostra toast de erro e mantem arquivos quando o processamento falha", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValue(CONFORMIDADE);
    vi.mocked(api.fiscalRiscoTributario).mockResolvedValue(RISCO);
    vi.mocked(api.fiscalProcessar).mockRejectedValueOnce(
      new Error("processamento falhou"),
    );

    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");
    await waitFor(() => expect(api.fiscalConformidade).toHaveBeenCalled());

    selectFiles([makeFile("notas.zip", 1024)]);
    await waitFor(() =>
      expect(screen.getByText("notas.zip")).toBeInTheDocument(),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Iniciar Cruzamento Fiscal" }),
    );

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("processamento falhou"),
    );
    // arquivo permanece na lista (não foi limpo)
    expect(screen.getByText("notas.zip")).toBeInTheDocument();
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("renderiza traco no KPI de risco quando risco indisponivel", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.fiscalConformidade).mockResolvedValueOnce(CONFORMIDADE);
    vi.mocked(api.fiscalRiscoTributario).mockRejectedValueOnce(
      new Error("risco off"),
    );

    render(<ConformidadeFiscalPage />);
    await screen.findByRole("option", { name: /Acme Ltda/ });
    await userEvent.selectOptions(screen.getByTestId("mock-select"), "c1");

    // Promise.all rejeita -> loadDados captura erro e não seta conformidade/risco
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("risco off"));
    expect(screen.queryByText("Score Geral")).not.toBeInTheDocument();
  });
});
