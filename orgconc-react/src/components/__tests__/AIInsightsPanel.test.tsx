import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AIInsightsPanel } from "@/components/dashboard/AIInsightsPanel";
import type { AiInsight, AiInsightsResponse } from "@/lib/api";

// O componente é puramente apresentacional: recebe `data`, `loading` e
// `onRefresh` por props e NÃO importa nenhuma função de "@/lib/api"
// (apenas os tipos AiInsight/AiInsightsResponse). Por isso não há
// vi.mock("@/lib/api") — não existe função de API usada para mockar.

const INSIGHT_INFO: AiInsight = {
  tipo: "info",
  titulo: "Conciliação em dia",
  texto: "Nenhuma pendência relevante no período.",
  cta: null,
};

const INSIGHT_WARN: AiInsight = {
  tipo: "warn",
  titulo: "Anomalias detectadas",
  texto: "8 transações fora do padrão esperado.",
  cta: "Revisar anomalias",
};

const INSIGHT_SUCCESS: AiInsight = {
  tipo: "success",
  titulo: "Taxa de acerto alta",
  texto: "97% das transações conciliadas automaticamente.",
  cta: null,
};

function makeData(overrides: Partial<AiInsightsResponse> = {}): AiInsightsResponse {
  return {
    insights: [INSIGHT_INFO],
    from_cache: false,
    gerado_em: "2026-06-09T12:00:00Z",
    expira_em: "2026-06-09T13:00:00Z",
    ...overrides,
  };
}

describe("AIInsightsPanel", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renderiza titulo e botao de atualizar", () => {
    render(<AIInsightsPanel data={null} loading={false} onRefresh={vi.fn()} />);
    expect(screen.getByText("Insights da IA")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /atualizar/i })).toBeInTheDocument();
  });

  it("mostra estado de carregamento quando loading e sem dados", () => {
    render(<AIInsightsPanel data={null} loading={true} onRefresh={vi.fn()} />);
    expect(screen.getByText("Consultando a IA…")).toBeInTheDocument();
    // botao fica desabilitado durante a consulta
    expect(screen.getByRole("button", { name: /atualizar/i })).toBeDisabled();
  });

  it("mostra empty state quando data é null", () => {
    render(<AIInsightsPanel data={null} loading={false} onRefresh={vi.fn()} />);
    expect(
      screen.getByText(/nenhum insight disponível\. faça uma conciliação para gerar análises\./i),
    ).toBeInTheDocument();
  });

  it("mostra empty state quando a lista de insights está vazia", () => {
    render(
      <AIInsightsPanel data={makeData({ insights: [] })} loading={false} onRefresh={vi.fn()} />,
    );
    expect(
      screen.getByText(/nenhum insight disponível\. faça uma conciliação para gerar análises\./i),
    ).toBeInTheDocument();
  });

  it("renderiza os insights retornados (titulo, texto e cta)", () => {
    render(
      <AIInsightsPanel
        data={makeData({ insights: [INSIGHT_INFO, INSIGHT_WARN, INSIGHT_SUCCESS] })}
        loading={false}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByText("Conciliação em dia")).toBeInTheDocument();
    expect(screen.getByText("Nenhuma pendência relevante no período.")).toBeInTheDocument();
    expect(screen.getByText("Anomalias detectadas")).toBeInTheDocument();
    expect(screen.getByText("8 transações fora do padrão esperado.")).toBeInTheDocument();
    expect(screen.getByText("Taxa de acerto alta")).toBeInTheDocument();
    // CTA do insight com cta definido (acrescido de seta)
    expect(screen.getByRole("button", { name: /revisar anomalias/i })).toBeInTheDocument();
  });

  it("não renderiza botão de CTA para insight com cta null", () => {
    render(
      <AIInsightsPanel
        data={makeData({ insights: [INSIGHT_INFO] })}
        loading={false}
        onRefresh={vi.fn()}
      />,
    );
    // Só o botão "Atualizar" existe; nenhum botão de CTA (cta é null)
    const botoes = screen.getAllByRole("button");
    expect(botoes).toHaveLength(1);
    expect(botoes[0]).toHaveAccessibleName(/atualizar/i);
  });

  it("exibe selo 'novo' quando os dados não vêm do cache", () => {
    render(
      <AIInsightsPanel data={makeData({ from_cache: false })} loading={false} onRefresh={vi.fn()} />,
    );
    expect(screen.getByText("novo")).toBeInTheDocument();
    expect(screen.queryByText("cache")).not.toBeInTheDocument();
  });

  it("exibe selo 'cache' quando os dados vêm do cache", () => {
    render(
      <AIInsightsPanel data={makeData({ from_cache: true })} loading={false} onRefresh={vi.fn()} />,
    );
    expect(screen.getByText("cache")).toBeInTheDocument();
    expect(screen.queryByText("novo")).not.toBeInTheDocument();
  });

  it("não exibe selo de cache/novo quando data é null", () => {
    render(<AIInsightsPanel data={null} loading={false} onRefresh={vi.fn()} />);
    expect(screen.queryByText("cache")).not.toBeInTheDocument();
    expect(screen.queryByText("novo")).not.toBeInTheDocument();
  });

  it("dispara onRefresh ao clicar em Atualizar", async () => {
    const onRefresh = vi.fn();
    const user = userEvent.setup();
    render(
      <AIInsightsPanel data={makeData()} loading={false} onRefresh={onRefresh} />,
    );
    await user.click(screen.getByRole("button", { name: /atualizar/i }));
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
  });

  it("desabilita o botão Atualizar enquanto loading (mesmo com dados em tela)", () => {
    render(<AIInsightsPanel data={makeData()} loading={true} onRefresh={vi.fn()} />);
    // Com dados presentes, ainda mostra os insights (não o estado de carregamento)
    expect(screen.getByText("Conciliação em dia")).toBeInTheDocument();
    expect(screen.queryByText("Consultando a IA…")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /atualizar/i })).toBeDisabled();
  });
});
