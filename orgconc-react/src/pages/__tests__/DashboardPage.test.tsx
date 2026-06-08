import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "@/pages/DashboardPage";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchDashboardBundle: vi.fn(),
    fetchTrustScore: vi.fn(),
    fetchAiInsights: vi.fn(),
    fetchActivityFeed: vi.fn(),
    fetchAuditTimeline: vi.fn(),
  };
});

import * as api from "@/lib/api";

const BUNDLE = {
  kpis: {
    volume_total: 1_500_000,
    transacoes: 1200,
    anomalias: 8,
    conciliacoes: 42,
    periodo_dias: 30,
    taxa_anomalias_pct: 0.7,
    delta: { transacoes_pct: 5, conciliacoes_pct: 2, anomalias_pct: -1 },
  },
  trend: [],
  distribuicao: [],
  heatmap: [],
} as unknown as api.DashboardBundle;

function renderDash() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("busca todos os dados do dashboard ao montar", async () => {
    vi.mocked(api.fetchDashboardBundle).mockResolvedValue(BUNDLE);
    vi.mocked(api.fetchTrustScore).mockResolvedValue(null as unknown as api.TrustScore);
    vi.mocked(api.fetchAiInsights).mockResolvedValue(null as unknown as api.AiInsightsResponse);
    vi.mocked(api.fetchActivityFeed).mockResolvedValue([]);
    vi.mocked(api.fetchAuditTimeline).mockResolvedValue(null as unknown as api.AuditTimelineResponse);

    renderDash();
    await waitFor(() => expect(api.fetchDashboardBundle).toHaveBeenCalledWith(30));
    expect(api.fetchTrustScore).toHaveBeenCalled();
    expect(api.fetchActivityFeed).toHaveBeenCalled();
  });

  it("exibe titulo e KPIs apos carregar o bundle", async () => {
    vi.mocked(api.fetchDashboardBundle).mockResolvedValue(BUNDLE);
    vi.mocked(api.fetchTrustScore).mockResolvedValue(null as unknown as api.TrustScore);
    vi.mocked(api.fetchAiInsights).mockResolvedValue(null as unknown as api.AiInsightsResponse);
    vi.mocked(api.fetchActivityFeed).mockResolvedValue([]);
    vi.mocked(api.fetchAuditTimeline).mockResolvedValue(null as unknown as api.AuditTimelineResponse);

    renderDash();
    await waitFor(() =>
      expect(screen.getByText("Volume processado")).toBeInTheDocument(),
    );
    expect(screen.getByText("Anomalias detectadas")).toBeInTheDocument();
  });

  it("mostra estado de erro (nao o onboarding) se o bundle falhar", async () => {
    vi.mocked(api.fetchDashboardBundle).mockRejectedValue(new Error("500"));
    vi.mocked(api.fetchTrustScore).mockRejectedValue(new Error("500"));
    vi.mocked(api.fetchAiInsights).mockRejectedValue(new Error("500"));
    vi.mocked(api.fetchActivityFeed).mockRejectedValue(new Error("500"));
    vi.mocked(api.fetchAuditTimeline).mockRejectedValue(new Error("500"));

    renderDash();
    // Falha de API NÃO pode virar "Importe o primeiro extrato" (onboarding) —
    // mostra erro com retry, sem quebrar.
    await waitFor(() =>
      expect(screen.getByText("Não foi possível carregar o dashboard")).toBeInTheDocument(),
    );
    expect(screen.getByText("Tentar novamente")).toBeInTheDocument();
    expect(screen.queryByText(/Importe o primeiro extrato/i)).not.toBeInTheDocument();
  });
});
