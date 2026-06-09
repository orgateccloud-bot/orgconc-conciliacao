import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MatchersPage } from "@/pages/MatchersPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listarClientes: vi.fn(),
    conciliarMatchers: vi.fn(),
  };
});

// sonner não precisa de provider, mas mockamos para inspecionar os toasts.
const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    error: (msg: string) => toastError(msg),
    success: (msg: string) => toastSuccess(msg),
  },
}));

import * as api from "@/lib/api";

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

const DISPOSICAO: api.DisposicaoItem = {
  data: "2026-01-15",
  tipo: "DEBIT",
  valor: -1234.56,
  fitid: "f1",
  memo: "PAGAMENTO FORNECEDOR",
  nome: "FORNECEDOR XYZ",
  estagio: 2,
  disposicao: "RESOLVIDO_NFE",
  contraparte: "Fornecedor XYZ Ltda",
  conta_contabil: "1.1.01",
  origem: "nfe",
  flag: null,
  nfe_chave: "352601...",
};

const DISPOSICAO_PENDENTE: api.DisposicaoItem = {
  data: "2026-01-16",
  tipo: "CREDIT",
  valor: 500,
  fitid: "f2",
  memo: "DEPOSITO DESCONHECIDO",
  nome: "",
  estagio: 6,
  disposicao: "PENDENTE_REVISAO",
  contraparte: null,
  conta_contabil: null,
  origem: null,
  flag: "revisar",
  nfe_chave: null,
};

const RESPONSE: api.MatchersResponse = {
  cliente_id: "c1",
  total_transacoes: 2,
  automatizadas: 1,
  taxa_automatizacao_pct: 50,
  disposicoes: [DISPOSICAO, DISPOSICAO_PENDENTE],
  xmls_indexados: 3,
};

function ofx(name = "extrato.ofx") {
  return new File(["<OFX></OFX>"], name, { type: "application/x-ofx" });
}

describe("MatchersPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    toastError.mockReset();
    toastSuccess.mockReset();
  });

  it("renderiza o hero e dispara o fetch de clientes ao montar", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    render(<MatchersPage />);

    expect(screen.getByText("Conciliação contábil")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /executar conciliação/i }),
    ).toBeInTheDocument();
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalledTimes(1));
  });

  it("mostra toast de erro se a carga de clientes falhar (sem quebrar)", async () => {
    vi.mocked(api.listarClientes).mockRejectedValueOnce(new Error("500"));
    render(<MatchersPage />);

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Falha ao carregar clientes"),
    );
    // a página continua de pé
    expect(screen.getByText("Conciliação contábil")).toBeInTheDocument();
  });

  it("adiciona arquivos via input e permite remover", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    const user = userEvent.setup();
    const { container } = render(<MatchersPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(input, ofx("extrato.ofx"));

    expect(screen.getByText("extrato.ofx")).toBeInTheDocument();
    // a extensão é exibida como badge
    expect(screen.getByText("ofx")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /remover arquivo/i }));
    expect(screen.queryByText("extrato.ofx")).not.toBeInTheDocument();
  });

  it("o botão executar fica desabilitado sem cliente e sem arquivos", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    render(<MatchersPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    expect(
      screen.getByRole("button", { name: /executar conciliação/i }),
    ).toBeDisabled();
    expect(api.conciliarMatchers).not.toHaveBeenCalled();
  });

  it("seleciona cliente, envia arquivo, executa e renderiza KPIs + disposições", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.conciliarMatchers).mockResolvedValueOnce(RESPONSE);
    const user = userEvent.setup();
    const { container } = render(<MatchersPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    // seleciona cliente no Radix Select
    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText(/Acme Ltda/));

    // envia arquivo
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(input, ofx());

    // executa
    const btn = screen.getByRole("button", { name: /executar conciliação/i });
    await waitFor(() => expect(btn).toBeEnabled());
    await user.click(btn);

    await waitFor(() =>
      expect(api.conciliarMatchers).toHaveBeenCalledWith("c1", [
        expect.any(File),
      ]),
    );

    // KPIs
    await waitFor(() => expect(screen.getByText("Total")).toBeInTheDocument());
    expect(screen.getByText("Automatizadas")).toBeInTheDocument();
    expect(screen.getByText("Pendentes")).toBeInTheDocument();
    expect(screen.getByText("Taxa")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();

    // toast de sucesso
    expect(toastSuccess).toHaveBeenCalledWith("1/2 automatizadas (50%)");

    // tabela de disposições
    expect(screen.getByText("RESOLVIDO_NFE")).toBeInTheDocument();
    expect(screen.getByText("PENDENTE_REVISAO")).toBeInTheDocument();
    expect(screen.getByText("FORNECEDOR XYZ")).toBeInTheDocument();
  });

  it("filtra apenas pendentes e volta a mostrar todas", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.conciliarMatchers).mockResolvedValueOnce(RESPONSE);
    const user = userEvent.setup();
    const { container } = render(<MatchersPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText(/Acme Ltda/));
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(input, ofx());
    await user.click(
      screen.getByRole("button", { name: /executar conciliação/i }),
    );
    await waitFor(() =>
      expect(screen.getByText("RESOLVIDO_NFE")).toBeInTheDocument(),
    );

    // contador inicial "2 de 2"
    expect(screen.getByText("2 de 2")).toBeInTheDocument();

    // filtra apenas pendentes
    await user.click(
      screen.getByRole("button", { name: /apenas pendentes/i }),
    );
    expect(screen.getByText("PENDENTE_REVISAO")).toBeInTheDocument();
    expect(screen.queryByText("RESOLVIDO_NFE")).not.toBeInTheDocument();
    expect(screen.getByText("1 de 2")).toBeInTheDocument();

    // volta a mostrar todas
    await user.click(screen.getByRole("button", { name: /mostrar todas/i }));
    expect(screen.getByText("RESOLVIDO_NFE")).toBeInTheDocument();
  });

  it("mostra empty state da tabela quando o filtro não retorna nada", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.conciliarMatchers).mockResolvedValueOnce({
      ...RESPONSE,
      total_transacoes: 1,
      automatizadas: 1,
      disposicoes: [DISPOSICAO], // sem pendentes
    });
    const user = userEvent.setup();
    const { container } = render(<MatchersPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText(/Acme Ltda/));
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(input, ofx());
    await user.click(
      screen.getByRole("button", { name: /executar conciliação/i }),
    );
    await waitFor(() =>
      expect(screen.getByText("RESOLVIDO_NFE")).toBeInTheDocument(),
    );

    // filtrar pendentes -> nenhuma disposição corresponde
    await user.click(
      screen.getByRole("button", { name: /apenas pendentes/i }),
    );
    expect(
      screen.getByText("Nenhuma transação para exibir."),
    ).toBeInTheDocument();
  });

  it("mostra toast de erro se a conciliação falhar (sem quebrar)", async () => {
    vi.mocked(api.listarClientes).mockResolvedValueOnce([CLIENTE]);
    vi.mocked(api.conciliarMatchers).mockRejectedValueOnce(
      new Error("falha no upload"),
    );
    const user = userEvent.setup();
    const { container } = render(<MatchersPage />);
    await waitFor(() => expect(api.listarClientes).toHaveBeenCalled());

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText(/Acme Ltda/));
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(input, ofx());
    await user.click(
      screen.getByRole("button", { name: /executar conciliação/i }),
    );

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("falha no upload"),
    );
    // nenhum resultado renderizado
    expect(screen.queryByText("Total")).not.toBeInTheDocument();
    // página continua de pé
    expect(screen.getByText("Conciliação contábil")).toBeInTheDocument();
  });
});
