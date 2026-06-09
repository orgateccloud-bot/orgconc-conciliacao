import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { UploadPage } from "@/pages/UploadPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    conciliarOfx: vi.fn(),
    conciliarCsv: vi.fn(),
    salvarHistoricoLocal: vi.fn(),
  };
});

const navigateMock = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return { ...actual, useNavigate: () => navigateMock };
});

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

import * as api from "@/lib/api";

const RESPONSE = {
  modo: "simulacao",
  report_id: "rep-1",
  extratos: [{ arquivo: "extrato.ofx", conta: "001", qtd: 12 }],
  anomalias: [
    {
      severidade: "alta",
      tipo: "duplicidade",
      titulo: "Lançamento duplicado",
      conta: "001",
      valor: 100,
      detalhe: "x",
    },
  ],
  relatorio_md: "# md",
} as api.ConciliacaoResponse;

function makeFile(name: string, size = 1024) {
  const file = new File(["x".repeat(size)], name, { type: "text/plain" });
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

function renderUpload() {
  return render(
    <MemoryRouter>
      <UploadPage />
    </MemoryRouter>,
  );
}

describe("UploadPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("renderiza titulo, formatos e botao de iniciar desabilitado sem arquivos", () => {
    renderUpload();
    expect(screen.getByText("Enviar extratos para")).toBeInTheDocument();
    expect(screen.getByText("OFX · PDF · XML")).toBeInTheDocument();
    expect(screen.getByText("CSV (extrato + razão)")).toBeInTheDocument();
    expect(
      screen.getByText(/Arraste ou clique — OFX, PDF ou XML/i),
    ).toBeInTheDocument();
    const iniciar = screen.getByRole("button", { name: /iniciar conciliação/i });
    expect(iniciar).toBeDisabled();
  });

  it("alterna para o formato CSV e atualiza o texto da drop zone", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderUpload();
    await user.click(screen.getByText("CSV (extrato + razão)"));
    expect(
      screen.getByText(/Arraste ou clique — até 2 arquivos CSV/i),
    ).toBeInTheDocument();
  });

  it("mostra aviso de creditos ao selecionar o modo Opus", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderUpload();
    expect(
      screen.queryByText(/consome ~10× mais créditos/i),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Opus" }));
    expect(
      screen.getByText(/Opus consome ~10× mais créditos que Sonnet/i),
    ).toBeInTheDocument();
  });

  it("lista arquivos selecionados e habilita o botao de iniciar", async () => {
    renderUpload();
    selectFiles([makeFile("extrato.ofx", 2048)]);
    await waitFor(() =>
      expect(screen.getByText("extrato.ofx")).toBeInTheDocument(),
    );
    expect(screen.getByText("ofx")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /iniciar conciliação/i }),
    ).not.toBeDisabled();
  });

  it("remove um arquivo da lista", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderUpload();
    selectFiles([makeFile("extrato.ofx")]);
    await waitFor(() =>
      expect(screen.getByText("extrato.ofx")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /remover arquivo/i }));
    await waitFor(() =>
      expect(screen.queryByText("extrato.ofx")).not.toBeInTheDocument(),
    );
  });

  it("dispara conciliarOfx em simulacao, salva historico e navega ao concluir", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    vi.mocked(api.conciliarOfx).mockResolvedValueOnce(RESPONSE);
    renderUpload();
    selectFiles([makeFile("extrato.ofx")]);
    await waitFor(() =>
      expect(screen.getByText("extrato.ofx")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /iniciar conciliação/i }),
    );

    await waitFor(() => expect(api.conciliarOfx).toHaveBeenCalledTimes(1));
    expect(api.conciliarOfx).toHaveBeenCalledWith(expect.any(Array), {
      simular: true,
      multi_modelo: false,
      modelo: undefined,
    });
    expect(api.conciliarCsv).not.toHaveBeenCalled();
    expect(api.salvarHistoricoLocal).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "rep-1",
        modo: "simulacao",
        total_tx: 12,
        total_anom: 1,
      }),
    );
    expect(toastSuccess).toHaveBeenCalledWith(
      "Conciliação concluída — 1 anomalia(s)",
    );
    expect(navigateMock).toHaveBeenCalledWith("/conciliacao", {
      state: { resultado: RESPONSE },
    });
    expect(sessionStorage.getItem("orgconc.last_resultado")).toBe(
      JSON.stringify(RESPONSE),
    );
  });

  it("usa conciliarCsv quando o formato CSV esta selecionado", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    vi.mocked(api.conciliarCsv).mockResolvedValueOnce(RESPONSE);
    renderUpload();
    await user.click(screen.getByText("CSV (extrato + razão)"));
    selectFiles([makeFile("razao.csv")]);
    await waitFor(() => expect(screen.getByText("razao.csv")).toBeInTheDocument());
    await user.click(
      screen.getByRole("button", { name: /iniciar conciliação/i }),
    );
    await waitFor(() => expect(api.conciliarCsv).toHaveBeenCalledTimes(1));
    expect(api.conciliarOfx).not.toHaveBeenCalled();
  });

  it("envia o modelo escolhido nas opcoes quando o modo e um modelo Claude", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    vi.mocked(api.conciliarOfx).mockResolvedValueOnce(RESPONSE);
    renderUpload();
    await user.click(screen.getByRole("button", { name: "Sonnet" }));
    selectFiles([makeFile("extrato.ofx")]);
    await waitFor(() =>
      expect(screen.getByText("extrato.ofx")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /iniciar conciliação/i }),
    );
    await waitFor(() => expect(api.conciliarOfx).toHaveBeenCalledTimes(1));
    expect(api.conciliarOfx).toHaveBeenCalledWith(expect.any(Array), {
      simular: false,
      multi_modelo: false,
      modelo: "sonnet",
    });
  });

  it("mostra toast de erro e nao navega se a conciliacao falhar", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    vi.mocked(api.conciliarOfx).mockRejectedValueOnce(new Error("falha API"));
    renderUpload();
    selectFiles([makeFile("extrato.ofx")]);
    await waitFor(() =>
      expect(screen.getByText("extrato.ofx")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /iniciar conciliação/i }),
    );
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("falha API"));
    expect(navigateMock).not.toHaveBeenCalled();
    expect(api.salvarHistoricoLocal).not.toHaveBeenCalled();
  });
});
