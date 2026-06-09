import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { AuditTimeline } from "@/components/dashboard/AuditTimeline";
import type { AuditEventSummary, AuditTimelineResponse } from "@/lib/api";

// Datas FIXAS (strings literais) — nada dinâmico, teste determinístico.
const evento = (over: Partial<AuditEventSummary> = {}): AuditEventSummary => ({
  id: "evt-1",
  ts: "2026-01-15T10:30:00.000Z",
  actor_email: "ana@orgatec.com",
  actor_sub: null,
  action: "login.success",
  resource_type: null,
  resource_id: null,
  payload_hash: "abc123def456abc123def456abc123def456abc123def456",
  prev_hash: "000000000000000000000000000000000000000000000000",
  payload_hash_short: "abc123de",
  request_id: "req-1",
  ...over,
});

const timeline = (over: Partial<AuditTimelineResponse> = {}): AuditTimelineResponse => ({
  total: 2,
  limit: 10,
  offset: 0,
  cadeia_integra: true,
  cadeia_motivo: null,
  eventos: [
    evento({ id: "evt-1", action: "login.success", actor_email: "ana@orgatec.com", payload_hash_short: "abc123de" }),
    evento({ id: "evt-2", action: "conciliacao.criar", actor_email: "bruno@orgatec.com", payload_hash_short: "ff00ee11" }),
  ],
  ...over,
});

describe("AuditTimeline", () => {
  it("mostra estado indisponível quando data é null", () => {
    render(<AuditTimeline data={null} />);
    expect(screen.getByText("Auditoria indisponível")).toBeInTheDocument();
  });

  it("mostra estado vazio quando não há eventos", () => {
    render(<AuditTimeline data={timeline({ total: 0, eventos: [] })} />);
    expect(screen.getByText(/Nenhum evento registrado ainda/)).toBeInTheDocument();
    // Cabeçalho continua presente mesmo sem eventos.
    expect(screen.getByText("Trilha de auditoria")).toBeInTheDocument();
    expect(screen.getByText("0 eventos")).toBeInTheDocument();
  });

  it("renderiza cabeçalho, total e eventos quando há dados", () => {
    render(<AuditTimeline data={timeline()} />);
    expect(screen.getByText("Trilha de auditoria")).toBeInTheDocument();
    expect(screen.getByText("2 eventos")).toBeInTheDocument();
    // Ações são traduzidas para PT-BR via descrever().
    expect(screen.getByText("Login bem-sucedido")).toBeInTheDocument();
    expect(screen.getByText("Conciliação criada")).toBeInTheDocument();
    // Ator e hash curto visíveis.
    expect(screen.getByText("ana@orgatec.com")).toBeInTheDocument();
    expect(screen.getByText("abc123de")).toBeInTheDocument();
  });

  it("exibe badge Íntegra quando a cadeia está íntegra", () => {
    render(<AuditTimeline data={timeline({ cadeia_integra: true, cadeia_motivo: null })} />);
    expect(screen.getByText("Íntegra")).toBeInTheDocument();
    expect(screen.queryByText("Comprometida")).not.toBeInTheDocument();
  });

  it("exibe badge Comprometida quando a cadeia está quebrada", () => {
    render(
      <AuditTimeline
        data={timeline({ cadeia_integra: false, cadeia_motivo: "Hash divergente no evento evt-2" })}
      />,
    );
    expect(screen.getByText("Comprometida")).toBeInTheDocument();
    expect(screen.queryByText("Íntegra")).not.toBeInTheDocument();
  });

  it("expõe cada evento como um botão acessível (role button)", () => {
    render(<AuditTimeline data={timeline()} />);
    // Cada linha de evento é um <button> clicável → 2 eventos = 2 botões.
    const botoes = screen.getAllByRole("button");
    expect(botoes).toHaveLength(2);
  });
});
