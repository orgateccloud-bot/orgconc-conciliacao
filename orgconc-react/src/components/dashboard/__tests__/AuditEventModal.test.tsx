import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

import { AuditEventModal } from "@/components/dashboard/AuditEventModal";
import { ApiError, type AuditEventDetalhe } from "@/lib/api";

// O componente chama fetchAuditEvento(evento_id) dentro de um useEffect.
// Mockamos APENAS essa função do módulo @/lib/api, preservando o resto
// (ApiError, tipos) via importação real (orig). Cada caso controla o que
// fetchAuditEvento resolve/rejeita — determinístico, sem rede.
const { fetchAuditEventoMock } = vi.hoisted(() => ({
  fetchAuditEventoMock: vi.fn(),
}));

vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  fetchAuditEvento: fetchAuditEventoMock,
}));

// Detalhe determinístico — datas e hashes são strings literais fixas.
const EVENTO: AuditEventDetalhe = {
  id: "evt_123",
  // ISO fixo em UTC; o componente formata via toLocaleString("pt-BR"),
  // por isso NÃO assertamos a data formatada (depende do TZ do runner).
  ts: "2026-01-15T12:00:00.000Z",
  actor_email: "ana@orgatec.com",
  actor_sub: "sub-1",
  action: "fiscal.laudo.gerar",
  resource_type: "laudo",
  resource_id: "lau_99",
  payload_hash: "aaaabbbbcccc",
  prev_hash: "0000ffff1111",
  payload_hash_short: "aaaa",
  request_id: "req_abc",
  payload: { campo: "valor", numero: 42 },
  payload_hash_valid: true,
};

describe("AuditEventModal", () => {
  beforeEach(() => {
    fetchAuditEventoMock.mockReset();
  });

  it("exibe estado de carregando enquanto a busca não resolve", () => {
    // Promise que nunca resolve → permanece em loading.
    fetchAuditEventoMock.mockReturnValue(new Promise(() => {}));
    render(<AuditEventModal evento_id="evt_123" onClose={vi.fn()} />);

    expect(screen.getByText("Carregando…")).toBeInTheDocument();
    // Título do modal sempre presente.
    expect(screen.getByText("Evento de auditoria")).toBeInTheDocument();
  });

  it("renderiza os detalhes do evento quando a busca resolve", async () => {
    fetchAuditEventoMock.mockResolvedValue(EVENTO);
    render(<AuditEventModal evento_id="evt_123" onClose={vi.fn()} />);

    // findBy* aguarda o resolve do useEffect.
    expect(await screen.findByText("fiscal.laudo.gerar")).toBeInTheDocument();
    expect(screen.getByText("ana@orgatec.com")).toBeInTheDocument();
    expect(screen.getByText("req_abc")).toBeInTheDocument();
    expect(screen.getByText("aaaabbbbcccc")).toBeInTheDocument();
    // Labels das linhas.
    expect(screen.getByText("Ação")).toBeInTheDocument();
    expect(screen.getByText("Request ID")).toBeInTheDocument();
    // O estado de loading sumiu.
    expect(screen.queryByText("Carregando…")).not.toBeInTheDocument();
  });

  it("mostra hash chain íntegro quando payload_hash_valid é true", async () => {
    fetchAuditEventoMock.mockResolvedValue(EVENTO);
    render(<AuditEventModal evento_id="evt_123" onClose={vi.fn()} />);

    expect(await screen.findByText("íntegro")).toBeInTheDocument();
    expect(screen.queryByText("comprometido")).not.toBeInTheDocument();
  });

  it("mostra hash chain comprometido quando payload_hash_valid é false", async () => {
    fetchAuditEventoMock.mockResolvedValue({ ...EVENTO, payload_hash_valid: false });
    render(<AuditEventModal evento_id="evt_123" onClose={vi.fn()} />);

    expect(await screen.findByText("comprometido")).toBeInTheDocument();
    expect(screen.queryByText("íntegro")).not.toBeInTheDocument();
  });

  it("exibe a mensagem de erro quando a busca falha com ApiError", async () => {
    fetchAuditEventoMock.mockRejectedValue(new ApiError("Evento não encontrado", 404));
    render(<AuditEventModal evento_id="evt_999" onClose={vi.fn()} />);

    expect(await screen.findByText("Evento não encontrado")).toBeInTheDocument();
    // Em erro não há loading nem detalhe.
    expect(screen.queryByText("Carregando…")).not.toBeInTheDocument();
  });

  it("expõe o modal com role=dialog acessível", async () => {
    fetchAuditEventoMock.mockResolvedValue(EVENTO);
    render(<AuditEventModal evento_id="evt_123" onClose={vi.fn()} />);

    // Radix Dialog renderiza role="dialog"; aguardamos o conteúdo carregar.
    expect(await screen.findByText("fiscal.laudo.gerar")).toBeInTheDocument();
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
  });
});
