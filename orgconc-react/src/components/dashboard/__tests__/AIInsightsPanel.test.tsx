import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { AIInsightsPanel } from "@/components/dashboard/AIInsightsPanel";
import type { AiInsightsResponse } from "@/lib/api";

// Datas FIXAS (strings literais) — sem valores dinâmicos, teste determinístico.
const RESPONSE_COM_DADOS: AiInsightsResponse = {
  insights: [
    {
      tipo: "success",
      titulo: "Conciliação saudável",
      texto: "Taxa de sucesso de 98% no período analisado.",
      cta: "Ver detalhes",
    },
    {
      tipo: "warn",
      titulo: "Anomalias detectadas",
      texto: "3 lançamentos divergentes precisam de revisão.",
      cta: null,
    },
  ],
  from_cache: false,
  gerado_em: "2026-06-09T10:00:00.000Z",
  expira_em: "2026-06-09T11:00:00.000Z",
};

const RESPONSE_VAZIA: AiInsightsResponse = {
  insights: [],
  from_cache: true,
  gerado_em: "2026-06-09T10:00:00.000Z",
  expira_em: "2026-06-09T11:00:00.000Z",
};

describe("AIInsightsPanel", () => {
  it("renderiza o cabeçalho e os insights quando há dados", () => {
    render(<AIInsightsPanel data={RESPONSE_COM_DADOS} loading={false} onRefresh={vi.fn()} />);

    expect(screen.getByText("Insights da IA")).toBeInTheDocument();
    expect(screen.getByText("Conciliação saudável")).toBeInTheDocument();
    expect(screen.getByText("Taxa de sucesso de 98% no período analisado.")).toBeInTheDocument();
    expect(screen.getByText("Anomalias detectadas")).toBeInTheDocument();
    // CTA renderizado com a seta apenas no insight que tem cta.
    expect(screen.getByText(/Ver detalhes/)).toBeInTheDocument();
  });

  it("exibe o badge 'novo' quando o resultado não vem do cache", () => {
    render(<AIInsightsPanel data={RESPONSE_COM_DADOS} loading={false} onRefresh={vi.fn()} />);
    expect(screen.getByText("novo")).toBeInTheDocument();
    expect(screen.queryByText("cache")).not.toBeInTheDocument();
  });

  it("mostra estado de carregamento quando loading e ainda sem dados", () => {
    render(<AIInsightsPanel data={null} loading={true} onRefresh={vi.fn()} />);
    expect(screen.getByText(/Consultando a IA/)).toBeInTheDocument();
    expect(screen.queryByText("novo")).not.toBeInTheDocument();
    expect(screen.queryByText("cache")).not.toBeInTheDocument();
  });

  it("mostra estado vazio quando não há insights", () => {
    render(<AIInsightsPanel data={RESPONSE_VAZIA} loading={false} onRefresh={vi.fn()} />);
    expect(screen.getByText(/Nenhum insight disponível/)).toBeInTheDocument();
    // Badge 'cache' aparece porque RESPONSE_VAZIA.from_cache === true.
    expect(screen.getByText("cache")).toBeInTheDocument();
  });

  it("dispara onRefresh ao clicar em 'Atualizar' e desabilita o botão durante o loading", () => {
    const onRefresh = vi.fn();
    const { rerender } = render(
      <AIInsightsPanel data={RESPONSE_COM_DADOS} loading={false} onRefresh={onRefresh} />,
    );

    // Acessibilidade: o controle é um <button> (role) com title descritivo.
    const botao = screen.getByRole("button", { name: /Atualizar/ });
    expect(botao).toHaveAttribute("title", "Forçar nova geração via Claude");
    expect(botao).toBeEnabled();

    botao.click();
    expect(onRefresh).toHaveBeenCalledTimes(1);

    rerender(<AIInsightsPanel data={RESPONSE_COM_DADOS} loading={true} onRefresh={onRefresh} />);
    expect(screen.getByRole("button", { name: /Atualizar/ })).toBeDisabled();
  });
});
