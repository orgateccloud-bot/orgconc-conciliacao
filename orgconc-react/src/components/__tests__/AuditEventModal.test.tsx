import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuditEventModal } from "@/components/dashboard/AuditEventModal";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchAuditEvento: vi.fn(),
  };
});

import * as api from "@/lib/api";

const EVENTO: api.AuditEventDetalhe = {
  id: "ev1",
  ts: "2026-06-09T12:00:00Z",
  actor_email: "auditor@orgatec.com",
  actor_sub: "sub-123",
  action: "fiscal.laudo.gerar",
  resource_type: "laudo",
  resource_id: "laudo-7",
  payload_hash: "abc123def456",
  prev_hash: "000prev999",
  payload_hash_short: "abc123",
  request_id: "req-xyz",
  payload: { campo: "valor", numero: 42 },
  payload_hash_valid: true,
};

describe("AuditEventModal", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("busca o evento pelo id ao montar e mostra o titulo", async () => {
    vi.mocked(api.fetchAuditEvento).mockResolvedValueOnce(EVENTO);
    render(<AuditEventModal evento_id="ev1" onClose={vi.fn()} />);

    expect(screen.getByText("Evento de auditoria")).toBeInTheDocument();
    await waitFor(() => expect(api.fetchAuditEvento).toHaveBeenCalledWith("ev1"));
    expect(api.fetchAuditEvento).toHaveBeenCalledTimes(1);
  });

  it("mostra estado de carregando antes da resposta", () => {
    // promise que nunca resolve → fica no estado de carregando
    vi.mocked(api.fetchAuditEvento).mockReturnValueOnce(new Promise(() => {}));
    render(<AuditEventModal evento_id="ev1" onClose={vi.fn()} />);

    expect(screen.getByText("Carregando…")).toBeInTheDocument();
    expect(screen.queryByText("Ação")).not.toBeInTheDocument();
  });

  it("renderiza os dados do evento retornado (aberto com evento)", async () => {
    vi.mocked(api.fetchAuditEvento).mockResolvedValueOnce(EVENTO);
    render(<AuditEventModal evento_id="ev1" onClose={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByText("fiscal.laudo.gerar")).toBeInTheDocument(),
    );
    expect(screen.getByText("Ação")).toBeInTheDocument();
    expect(screen.getByText("auditor@orgatec.com")).toBeInTheDocument();
    expect(screen.getByText("laudo · laudo-7")).toBeInTheDocument();
    expect(screen.getByText("req-xyz")).toBeInTheDocument();
    expect(screen.getByText("abc123def456")).toBeInTheDocument();
    expect(screen.getByText("000prev999")).toBeInTheDocument();
    // sumiu o estado de carregando
    expect(screen.queryByText("Carregando…")).not.toBeInTheDocument();
  });

  it("indica cadeia integra quando payload_hash_valid e true", async () => {
    vi.mocked(api.fetchAuditEvento).mockResolvedValueOnce(EVENTO);
    render(<AuditEventModal evento_id="ev1" onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("íntegro")).toBeInTheDocument());
    expect(screen.queryByText("comprometido")).not.toBeInTheDocument();
  });

  it("indica cadeia comprometida quando payload_hash_valid e false", async () => {
    vi.mocked(api.fetchAuditEvento).mockResolvedValueOnce({
      ...EVENTO,
      payload_hash_valid: false,
    });
    render(<AuditEventModal evento_id="ev1" onClose={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByText("comprometido")).toBeInTheDocument(),
    );
    expect(screen.queryByText("íntegro")).not.toBeInTheDocument();
  });

  it("usa o ator de fallback 'sistema' quando nao ha email nem sub", async () => {
    vi.mocked(api.fetchAuditEvento).mockResolvedValueOnce({
      ...EVENTO,
      actor_email: null,
      actor_sub: null,
    });
    render(<AuditEventModal evento_id="ev1" onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("sistema")).toBeInTheDocument());
  });

  it("mostra a mensagem da ApiError quando o fetch rejeita com ApiError", async () => {
    vi.mocked(api.fetchAuditEvento).mockRejectedValueOnce(
      new api.ApiError("Evento não encontrado", 404),
    );
    render(<AuditEventModal evento_id="ev1" onClose={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByText("Evento não encontrado")).toBeInTheDocument(),
    );
    // erro não vira tela de carregando nem de dados
    expect(screen.queryByText("Carregando…")).not.toBeInTheDocument();
    expect(screen.queryByText("Ação")).not.toBeInTheDocument();
  });

  it("mostra mensagem generica quando o fetch rejeita com erro nao-ApiError", async () => {
    vi.mocked(api.fetchAuditEvento).mockRejectedValueOnce(new Error("boom"));
    render(<AuditEventModal evento_id="ev1" onClose={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByText("Falha ao carregar evento")).toBeInTheDocument(),
    );
  });

  it("dispara onClose ao acionar o botao de fechar do dialog", async () => {
    const onClose = vi.fn();
    vi.mocked(api.fetchAuditEvento).mockResolvedValueOnce(EVENTO);
    render(<AuditEventModal evento_id="ev1" onClose={onClose} />);

    await waitFor(() => expect(screen.getByText("fiscal.laudo.gerar")).toBeInTheDocument());

    const closeBtn = screen.getByRole("button", { name: /close/i });
    await userEvent.click(closeBtn);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("dispara onClose ao pressionar Escape (onOpenChange -> false)", async () => {
    const onClose = vi.fn();
    vi.mocked(api.fetchAuditEvento).mockResolvedValueOnce(EVENTO);
    render(<AuditEventModal evento_id="ev1" onClose={onClose} />);

    await waitFor(() => expect(screen.getByText("fiscal.laudo.gerar")).toBeInTheDocument());

    await userEvent.keyboard("{Escape}");

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });
});
