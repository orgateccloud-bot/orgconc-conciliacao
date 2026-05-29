import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

import * as api from "@/lib/api";

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
});
