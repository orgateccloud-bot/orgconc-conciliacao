import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { TrendingUp } from "lucide-react";

import { KpiCard } from "@/components/dashboard/KpiCard";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { SecurityRing } from "@/components/dashboard/SecurityRing";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { AuthProvider } from "@/lib/auth";
import type { ActivityFeedItem, TrustScore } from "@/lib/api";

vi.mock("@/lib/theme", () => ({
  useTheme: () => ({ tema: "light", toggle: vi.fn() }),
}));

// O Sidebar usa useAuth() (gating do item admin "Usuários"); no app vive sempre
// dentro do AuthProvider. fetchMe falha cedo (sem rede) → user=null, sem item admin.
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  fetchMe: vi.fn().mockRejectedValue(new Error("sem sessão")),
}));

describe("KpiCard", () => {
  it("exibe label, valor e descrição", () => {
    render(
      <KpiCard label="Volume processado" value="R$ 1.5M" desc="1.2k transações" delta={null} icon={TrendingUp} accent="primary" />,
    );
    expect(screen.getByText("Volume processado")).toBeInTheDocument();
    expect(screen.getByText("R$ 1.5M")).toBeInTheDocument();
    expect(screen.getByText("1.2k transações")).toBeInTheDocument();
  });

  it("renderiza percentual quando delta é positivo", () => {
    render(<KpiCard label="X" value="10" delta={5.4} icon={TrendingUp} accent="green" />);
    expect(screen.getByText("5.4%")).toBeInTheDocument();
  });

  it("renderiza 0% quando delta é zero", () => {
    render(<KpiCard label="X" value="10" delta={0} icon={TrendingUp} accent="green" />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });
});

describe("ActivityFeed", () => {
  it("mostra estado vazio sem eventos", () => {
    render(<ActivityFeed data={[]} />);
    expect(screen.getByText(/Nenhum evento ainda/)).toBeInTheDocument();
  });

  it("lista os eventos com título e ator", () => {
    const items: ActivityFeedItem[] = [
      { id: "1", severidade: "success", titulo: "Conciliação concluída", ator: "ana@x.com", ts: new Date().toISOString() } as ActivityFeedItem,
    ];
    render(<ActivityFeed data={items} />);
    expect(screen.getByText("Conciliação concluída")).toBeInTheDocument();
    expect(screen.getByText(/ana@x.com/)).toBeInTheDocument();
  });
});

describe("SecurityRing (Trust Score)", () => {
  it("mostra estado sem dados", () => {
    render(<SecurityRing data={null} />);
    expect(screen.getByText("Calculando indicadores…")).toBeInTheDocument();
    expect(screen.getByText("Sem dados")).toBeInTheDocument();
    // Regressão: sem dados, "Controle de risco" não pode aparecer cheio (100%).
    expect(screen.queryByText("100.0%")).not.toBeInTheDocument();
  });

  it("mostra score, descrição e indicadores quando há dados", () => {
    const trust = {
      score: 80,
      periodo_dias: 30,
      descricao: "Saudável",
      breakdown: { taxa_sucesso_pct: 98, dias_sem_falha: 30, cobertura_pct: 50 },
      metricas: { total_conciliacoes: 12, taxa_anomalias_pct: 1.5 },
    } as unknown as TrustScore;
    render(<SecurityRing data={trust} />);
    expect(screen.getByText("80")).toBeInTheDocument();
    expect(screen.getByText("Saudável")).toBeInTheDocument();
    expect(screen.getByText("Taxa de sucesso")).toBeInTheDocument();
    expect(screen.getByText("Cobertura operacional")).toBeInTheDocument();
  });
});

describe("Sidebar", () => {
  function renderSidebar(props?: { anomalias?: number; clientes?: number }) {
    return render(
      <AuthProvider>
        <MemoryRouter>
          <Sidebar {...props} />
        </MemoryRouter>
      </AuthProvider>,
    );
  }

  it("renderiza os grupos de navegação", () => {
    renderSidebar();
    expect(screen.getByText("Operação")).toBeInTheDocument();
    expect(screen.getByText("Fiscal")).toBeInTheDocument();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
    expect(screen.getByText("Clientes")).toBeInTheDocument();
  });

  it("mostra badge de anomalias quando maior que zero", () => {
    renderSidebar({ anomalias: 7 });
    expect(screen.getByText("7")).toBeInTheDocument();
  });
});

describe("Topbar", () => {
  it("mostra título e status do banco online", () => {
    render(<Topbar title="Visão Geral" dbStatus="online" />);
    expect(screen.getByText("Visão Geral")).toBeInTheDocument();
    expect(screen.getByText("conectado")).toBeInTheDocument();
  });

  it("mostra as iniciais do usuário quando autenticado", () => {
    render(<Topbar title="X" dbStatus="offline" userEmail="bruno@orgatec.com" />);
    expect(screen.getByText("BR")).toBeInTheDocument();
    expect(screen.getByText("offline")).toBeInTheDocument();
  });
});
