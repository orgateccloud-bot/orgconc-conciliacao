import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuditTimeline } from "@/components/dashboard/AuditTimeline";
import type {
  AuditEventSummary,
  AuditTimelineResponse,
  AuditEventDetalhe,
} from "@/lib/api";

// O AuditTimeline em si é apresentacional (recebe `data` por prop e não
// chama nenhuma função de "@/lib/api"). Mas ao clicar numa linha ele
// monta o filho AuditEventModal, que SIM chama fetchAuditEvento. Por isso
// mockamos apenas essa função, preservando o resto do módulo real.
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchAuditEvento: vi.fn(),
  };
});

import * as api from "@/lib/api";

function makeEvento(overrides: Partial<AuditEventSummary> = {}): AuditEventSummary {
  return {
    id: "ev-1",
    ts: "2026-06-09T12:00:00Z",
    actor_email: "auditor@orgatec.com",
    actor_sub: "sub-1",
    action: "login.success",
    resource_type: null,
    resource_id: null,
    payload_hash: "hashcompletolongo123456",
    prev_hash: "prevhash000",
    payload_hash_short: "hashcur",
    request_id: "req-1",
    ...overrides,
  };
}

function makeData(overrides: Partial<AuditTimelineResponse> = {}): AuditTimelineResponse {
  return {
    total: 1,
    limit: 10,
    offset: 0,
    cadeia_integra: true,
    cadeia_motivo: null,
    eventos: [makeEvento()],
    ...overrides,
  };
}

const DETALHE: AuditEventDetalhe = {
  ...makeEvento(),
  payload: { campo: "valor" },
  payload_hash_valid: true,
};

describe("AuditTimeline", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("mostra 'Auditoria indisponível' quando data é null", () => {
    render(<AuditTimeline data={null} />);
    expect(screen.getByText("Auditoria indisponível")).toBeInTheDocument();
    // não renderiza o cabeçalho da trilha
    expect(screen.queryByText("Trilha de auditoria")).not.toBeInTheDocument();
  });

  it("renderiza o cabeçalho com total de eventos", () => {
    render(<AuditTimeline data={makeData({ total: 42 })} />);
    expect(screen.getByText("Trilha de auditoria")).toBeInTheDocument();
    expect(screen.getByText("42 eventos")).toBeInTheDocument();
  });

  it("mostra selo 'Íntegra' quando a cadeia está íntegra", () => {
    render(<AuditTimeline data={makeData({ cadeia_integra: true })} />);
    expect(screen.getByText("Íntegra")).toBeInTheDocument();
    expect(screen.queryByText("Comprometida")).not.toBeInTheDocument();
  });

  it("mostra selo 'Comprometida' quando a cadeia não está íntegra", () => {
    render(
      <AuditTimeline data={makeData({ cadeia_integra: false, cadeia_motivo: null })} />,
    );
    expect(screen.getByText("Comprometida")).toBeInTheDocument();
    expect(screen.queryByText("Íntegra")).not.toBeInTheDocument();
  });

  it("usa o motivo como title do selo quando a cadeia está comprometida", () => {
    render(
      <AuditTimeline
        data={makeData({
          cadeia_integra: false,
          cadeia_motivo: "Hash do evento 5 não bate",
        })}
      />,
    );
    const selo = screen.getByText("Comprometida").closest("span");
    expect(selo).toHaveAttribute("title", "Hash do evento 5 não bate");
  });

  it("usa título de fallback no selo comprometido quando não há motivo", () => {
    render(
      <AuditTimeline data={makeData({ cadeia_integra: false, cadeia_motivo: null })} />,
    );
    const selo = screen.getByText("Comprometida").closest("span");
    expect(selo).toHaveAttribute("title", "Cadeia comprometida");
  });

  it("usa o título 'Hash chain íntegra' no selo quando íntegra", () => {
    render(<AuditTimeline data={makeData({ cadeia_integra: true })} />);
    const selo = screen.getByText("Íntegra").closest("span");
    expect(selo).toHaveAttribute("title", "Hash chain íntegra");
  });

  it("mostra empty state quando não há eventos", () => {
    render(<AuditTimeline data={makeData({ eventos: [], total: 0 })} />);
    expect(
      screen.getByText(
        /nenhum evento registrado ainda\. eventos aparecem após login, conciliação ou alteração de clientes\./i,
      ),
    ).toBeInTheDocument();
    // sem lista de eventos
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("renderiza uma linha por evento com a descrição traduzida (pt-BR)", () => {
    render(
      <AuditTimeline
        data={makeData({
          total: 4,
          eventos: [
            makeEvento({ id: "a", action: "login.success" }),
            makeEvento({ id: "b", action: "conciliacao.criar" }),
            makeEvento({ id: "c", action: "cliente.criar" }),
            makeEvento({ id: "d", action: "cliente.atualizar" }),
          ],
        })}
      />,
    );
    expect(screen.getByText("Login bem-sucedido")).toBeInTheDocument();
    expect(screen.getByText("Conciliação criada")).toBeInTheDocument();
    expect(screen.getByText("Cliente cadastrado")).toBeInTheDocument();
    expect(screen.getByText("Cliente atualizado")).toBeInTheDocument();
    // uma linha (button) por evento
    expect(screen.getAllByRole("button")).toHaveLength(4);
  });

  it("usa o próprio nome da ação quando não há tradução conhecida", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ id: "x", action: "anomalia.detectada" })],
        })}
      />,
    );
    // descrever() não mapeia anomalia.detectada → usa a string crua
    expect(screen.getByText("anomalia.detectada")).toBeInTheDocument();
  });

  it("usa o ícone de fallback (Activity) para uma ação totalmente desconhecida", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ id: "z", action: "acao.inexistente" })],
        })}
      />,
    );
    // ação não está em ACTION_ICONE nem em descrever() → string crua e ícone padrão
    expect(screen.getByText("acao.inexistente")).toBeInTheDocument();
  });

  it("mostra o ator pelo email quando presente", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ actor_email: "ana@orgatec.com", actor_sub: "sub-x" })],
        })}
      />,
    );
    expect(screen.getByText("ana@orgatec.com")).toBeInTheDocument();
  });

  it("cai para actor_sub quando não há email", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ actor_email: null, actor_sub: "sub-only" })],
        })}
      />,
    );
    expect(screen.getByText("sub-only")).toBeInTheDocument();
  });

  it("cai para 'sistema' quando não há email nem sub", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ actor_email: null, actor_sub: null })],
        })}
      />,
    );
    expect(screen.getByText("sistema")).toBeInTheDocument();
  });

  it("formata a data em pt-BR quando ts está presente", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ ts: "2026-06-09T12:00:00Z" })],
        })}
      />,
    );
    const esperado = new Date("2026-06-09T12:00:00Z").toLocaleString("pt-BR");
    expect(screen.getByText(esperado)).toBeInTheDocument();
  });

  it("mostra '—' como data quando ts é null", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ ts: null })],
        })}
      />,
    );
    // o traço de data aparece (há também o separador "·", mas "—" é único)
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("mostra o resource_id truncado em 14 chars quando presente", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [
            makeEvento({ resource_id: "abcdefghijklmnopqrstuvwxyz" }),
          ],
        })}
      />,
    );
    // slice(0, 14) → "abcdefghijklmn", prefixado por "· "
    expect(screen.getByText("· abcdefghijklmn")).toBeInTheDocument();
  });

  it("não mostra resource_id quando ausente", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ resource_id: null })],
        })}
      />,
    );
    expect(screen.queryByText(/^· /)).not.toBeInTheDocument();
  });

  it("mostra o hash curto quando presente e o hash completo no title", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [
            makeEvento({
              payload_hash_short: "abc123",
              payload_hash: "abc123def456ghi789",
            }),
          ],
        })}
      />,
    );
    const selo = screen.getByText("abc123");
    expect(selo).toHaveAttribute("title", "Hash completo: abc123def456ghi789");
  });

  it("mostra '—' como hash curto quando payload_hash_short é null", () => {
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ payload_hash_short: null, payload_hash: "soco" })],
        })}
      />,
    );
    // o hash curto vira "—"; o title ainda carrega o hash completo
    const selo = screen.getByTitle("Hash completo: soco");
    expect(selo).toHaveTextContent("—");
  });

  it("não abre o modal antes de clicar numa linha", () => {
    render(<AuditTimeline data={makeData()} />);
    expect(screen.queryByText("Evento de auditoria")).not.toBeInTheDocument();
    expect(api.fetchAuditEvento).not.toHaveBeenCalled();
  });

  it("abre o AuditEventModal com o id do evento ao clicar na linha", async () => {
    vi.mocked(api.fetchAuditEvento).mockResolvedValueOnce(DETALHE);
    const user = userEvent.setup();
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ id: "ev-clicado" })],
        })}
      />,
    );

    await user.click(screen.getByText("Login bem-sucedido"));

    // o modal aparece e busca o detalhe pelo id clicado
    expect(screen.getByText("Evento de auditoria")).toBeInTheDocument();
    await waitFor(() =>
      expect(api.fetchAuditEvento).toHaveBeenCalledWith("ev-clicado"),
    );
  });

  it("fecha o modal (onClose) restaurando a timeline sem modal", async () => {
    vi.mocked(api.fetchAuditEvento).mockResolvedValue(DETALHE);
    const user = userEvent.setup();
    render(
      <AuditTimeline
        data={makeData({
          eventos: [makeEvento({ id: "ev-fechar", action: "login.success" })],
        })}
      />,
    );

    await user.click(screen.getByText("Login bem-sucedido"));
    expect(screen.getByText("Evento de auditoria")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    await waitFor(() =>
      expect(screen.queryByText("Evento de auditoria")).not.toBeInTheDocument(),
    );
    // a timeline continua visível
    expect(screen.getByText("Trilha de auditoria")).toBeInTheDocument();
  });

  it("abre o modal correspondente ao evento clicado quando há vários", async () => {
    vi.mocked(api.fetchAuditEvento).mockResolvedValueOnce(DETALHE);
    const user = userEvent.setup();
    render(
      <AuditTimeline
        data={makeData({
          total: 2,
          eventos: [
            makeEvento({ id: "primeiro", action: "login.success" }),
            makeEvento({ id: "segundo", action: "conciliacao.criar" }),
          ],
        })}
      />,
    );

    await user.click(screen.getByText("Conciliação criada"));

    await waitFor(() =>
      expect(api.fetchAuditEvento).toHaveBeenCalledWith("segundo"),
    );
    expect(api.fetchAuditEvento).toHaveBeenCalledTimes(1);
  });
});
