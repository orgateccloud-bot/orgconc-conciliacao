import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import type { ActivityFeedItem } from "@/lib/api";

// Relógio FIXO: o componente calcula "há quanto tempo" via Date.now() em
// formatarRelativo(). Congelamos o tempo para tornar a saída determinística.
const AGORA_FIXO = new Date("2026-06-09T12:00:00.000Z");

beforeAll(() => {
  vi.useFakeTimers();
  vi.setSystemTime(AGORA_FIXO);
});

afterAll(() => {
  vi.useRealTimers();
});

// Eventos mockados com DATAS LITERAIS (nunca dinâmicas). Os offsets relativos
// ao relógio fixo acima são previsíveis:
//   11:58Z → 2 min atrás → "2 min"
//   09:00Z → 3 h atrás   → "3h"
const ITENS: ActivityFeedItem[] = [
  {
    id: "ev-1",
    ts: "2026-06-09T11:58:00.000Z",
    titulo: "Conciliação concluída",
    severidade: "success",
    ator: "ana@orgatec.com",
    resource_id: "conc-001",
  },
  {
    id: "ev-2",
    ts: "2026-06-09T09:00:00.000Z",
    titulo: "Cliente alterado",
    severidade: "warn",
    ator: "bruno@orgatec.com",
    resource_id: "cli-042",
  },
  {
    id: "ev-3",
    ts: null,
    titulo: "Login no sistema",
    severidade: "info",
    ator: "carla@orgatec.com",
    resource_id: null,
  },
];

describe("ActivityFeed", () => {
  it("renderiza o cabeçalho e a lista de eventos com título e ator", () => {
    render(<ActivityFeed data={ITENS} />);

    expect(screen.getByText("Atividade Auditada")).toBeInTheDocument();

    expect(screen.getByText("Conciliação concluída")).toBeInTheDocument();
    expect(screen.getByText("Cliente alterado")).toBeInTheDocument();
    expect(screen.getByText("Login no sistema")).toBeInTheDocument();

    expect(screen.getByText(/ana@orgatec\.com/)).toBeInTheDocument();
    expect(screen.getByText(/bruno@orgatec\.com/)).toBeInTheDocument();
  });

  it("formata o tempo relativo a partir do ts (relógio congelado)", () => {
    render(<ActivityFeed data={ITENS} />);

    // 11:58Z vs. 12:00Z → 2 min; 09:00Z vs. 12:00Z → 3h.
    expect(screen.getByText(/ana@orgatec\.com · 2 min/)).toBeInTheDocument();
    expect(screen.getByText(/bruno@orgatec\.com · 3h/)).toBeInTheDocument();
  });

  it("exibe '—' quando o evento não tem timestamp (ts nulo)", () => {
    render(<ActivityFeed data={ITENS} />);

    expect(screen.getByText(/carla@orgatec\.com · —/)).toBeInTheDocument();
  });

  it("mostra o estado vazio quando não há eventos", () => {
    render(<ActivityFeed data={[]} />);

    expect(screen.getByText(/Nenhum evento ainda/)).toBeInTheDocument();
    // Cabeçalho continua presente mesmo sem eventos.
    expect(screen.getByText("Atividade Auditada")).toBeInTheDocument();
  });

  it("é resiliente a severidade desconhecida (fallback para 'info')", () => {
    const itens = [
      {
        id: "ev-x",
        ts: "2026-06-09T11:59:30.000Z",
        titulo: "Evento de severidade inesperada",
        severidade: "critico",
        ator: "sistema@orgatec.com",
        resource_id: null,
      } as unknown as ActivityFeedItem,
    ];

    // Não deve lançar; usa o ícone de fallback (info) sem quebrar a render.
    expect(() => render(<ActivityFeed data={itens} />)).not.toThrow();
    expect(screen.getByText("Evento de severidade inesperada")).toBeInTheDocument();
  });

  it("renderiza a lista de eventos como um elemento semântico <ol> (acessibilidade)", () => {
    const { container } = render(<ActivityFeed data={ITENS} />);

    const lista = container.querySelector("ol");
    expect(lista).not.toBeNull();
    // role="listitem" é o role implícito de <li>; um por evento.
    expect(screen.getAllByRole("listitem")).toHaveLength(ITENS.length);
  });
});
