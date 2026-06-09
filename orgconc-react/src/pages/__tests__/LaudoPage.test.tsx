import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LaudoPage } from "@/pages/LaudoPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fiscalLaudo: vi.fn(),
    baixarBlob: vi.fn(),
  };
});

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import * as api from "@/lib/api";
import { toast } from "sonner";

const CNPJ_VALIDO = "11.222.333/0001-81"; // 14 dígitos após limpar

function ofx(name = "extrato.ofx") {
  return new File(["<OFX>"], name, { type: "application/x-ofx" });
}
function xml(name = "nfe.xml") {
  return new File(["<nfe>"], name, { type: "text/xml" });
}

function fileInput(): HTMLInputElement {
  // input[type=file] está oculto; pega-o pelo seletor do source (multiple + accept)
  const el = document.querySelector('input[type="file"]');
  if (!el) throw new Error("file input não encontrado");
  return el as HTMLInputElement;
}

describe("LaudoPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renderiza titulo, formatos e botao de gerar ao montar", () => {
    render(<LaudoPage />);
    expect(screen.getByText("Laudo Integrado")).toBeInTheDocument();
    expect(screen.getByText("CNPJ da entidade auditada")).toBeInTheDocument();
    // formato default = xlsx → rótulo do botão
    expect(screen.getByRole("button", { name: /gerar laudo \(xlsx\)/i })).toBeInTheDocument();
    // os três formatos disponíveis
    expect(screen.getByText("XLSX")).toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByText("HTML")).toBeInTheDocument();
  });

  it("erro de validacao quando CNPJ nao tem 14 digitos", async () => {
    const user = userEvent.setup();
    render(<LaudoPage />);
    await user.click(screen.getByRole("button", { name: /gerar laudo/i }));
    expect(toast.error).toHaveBeenCalledWith("Informe o CNPJ da entidade auditada (14 dígitos)");
    expect(api.fiscalLaudo).not.toHaveBeenCalled();
  });

  it("erro de validacao quando ha CNPJ valido mas nenhum OFX", async () => {
    const user = userEvent.setup();
    render(<LaudoPage />);
    await user.type(screen.getByLabelText("CNPJ da entidade auditada"), CNPJ_VALIDO);
    await user.click(screen.getByRole("button", { name: /gerar laudo/i }));
    expect(toast.error).toHaveBeenCalledWith("Envie ao menos 1 extrato OFX");
    expect(api.fiscalLaudo).not.toHaveBeenCalled();
  });

  it("lista os arquivos anexados e mostra os contadores OFX/Fiscais", async () => {
    const user = userEvent.setup();
    render(<LaudoPage />);
    await user.upload(fileInput(), [ofx("extrato.ofx"), xml("nfe.xml")]);

    expect(screen.getByText("extrato.ofx")).toBeInTheDocument();
    expect(screen.getByText("nfe.xml")).toBeInTheDocument();
    expect(screen.getByText("OFX: 1")).toBeInTheDocument();
    expect(screen.getByText("Fiscais (XML/ZIP): 1")).toBeInTheDocument();
    // aviso de documentos fiscais detectados
    expect(
      screen.getByText(/Documentos fiscais detectados/i),
    ).toBeInTheDocument();
  });

  it("remove um arquivo da lista", async () => {
    const user = userEvent.setup();
    render(<LaudoPage />);
    await user.upload(fileInput(), [ofx("extrato.ofx")]);
    expect(screen.getByText("extrato.ofx")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remover arquivo" }));
    await waitFor(() => expect(screen.queryByText("extrato.ofx")).not.toBeInTheDocument());
  });

  it("gera laudo XLSX: chama fiscalLaudo com os dados, baixa o blob e mostra sucesso", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["x"]);
    vi.mocked(api.fiscalLaudo).mockResolvedValueOnce({ blob, filename: "laudo.xlsx" });

    render(<LaudoPage />);
    await user.type(screen.getByLabelText("CNPJ da entidade auditada"), CNPJ_VALIDO);
    await user.type(screen.getByLabelText("Conta (opcional)"), "158083");
    await user.upload(fileInput(), [ofx("extrato.ofx")]);
    await user.click(screen.getByRole("button", { name: /gerar laudo \(xlsx\)/i }));

    await waitFor(() => expect(api.fiscalLaudo).toHaveBeenCalledTimes(1));
    expect(api.fiscalLaudo).toHaveBeenCalledWith(
      expect.objectContaining({
        empresaCnpj: "11222333000181",
        conta: "158083",
        formato: "xlsx",
        arquivos: expect.arrayContaining([expect.any(File)]),
      }),
    );
    expect(api.baixarBlob).toHaveBeenCalledWith(blob, "laudo.xlsx");
    expect(toast.success).toHaveBeenCalledWith("Laudo gerado: laudo.xlsx");
  });

  it("formato HTML: abre nova aba (window.open) ao inves de baixar", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["<html></html>"]);
    vi.mocked(api.fiscalLaudo).mockResolvedValueOnce({ blob, filename: "laudo.html" });
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:fake");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    render(<LaudoPage />);
    await user.type(screen.getByLabelText("CNPJ da entidade auditada"), CNPJ_VALIDO);
    await user.upload(fileInput(), [ofx("extrato.ofx")]);
    // seleciona o formato HTML
    await user.click(screen.getByText("HTML"));
    await user.click(screen.getByRole("button", { name: /gerar laudo \(html\)/i }));

    await waitFor(() => expect(api.fiscalLaudo).toHaveBeenCalledTimes(1));
    expect(api.fiscalLaudo).toHaveBeenCalledWith(expect.objectContaining({ formato: "html" }));
    expect(openSpy).toHaveBeenCalledWith("blob:fake", "_blank");
    expect(api.baixarBlob).not.toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledWith("Laudo gerado: laudo.html");

    openSpy.mockRestore();
  });

  it("trata erro de geracao sem quebrar (toast.error com a mensagem)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fiscalLaudo).mockRejectedValueOnce(new Error("Falha no servidor"));

    render(<LaudoPage />);
    await user.type(screen.getByLabelText("CNPJ da entidade auditada"), CNPJ_VALIDO);
    await user.upload(fileInput(), [ofx("extrato.ofx")]);
    await user.click(screen.getByRole("button", { name: /gerar laudo/i }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Falha no servidor"));
    expect(api.baixarBlob).not.toHaveBeenCalled();
    // botão volta ao estado normal (não fica preso em "Gerando laudo...")
    expect(screen.getByRole("button", { name: /gerar laudo \(xlsx\)/i })).toBeInTheDocument();
  });
});
