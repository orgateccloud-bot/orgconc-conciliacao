import { lazy, Suspense, useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Outlet,
  useLocation,
} from "react-router-dom";
import { ThemeProvider } from "@/lib/theme";
import { AuthProvider, useAuth } from "@/lib/auth";
import { fetchHealth, listarClientes, listarConciliacoes } from "@/lib/api";
import { LoginPage } from "@/pages/LoginPage";
import { Sidebar, SidebarNavContent } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { Toaster } from "@/components/ui/sonner";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PageSkeleton, AppBootSkeleton } from "@/components/skeletons";

const DashboardPage    = lazy(() => import("@/pages/DashboardPage").then(m => ({ default: m.DashboardPage })));
const ConciliacaoPage  = lazy(() => import("@/pages/ConciliacaoPage").then(m => ({ default: m.ConciliacaoPage })));
const ClientesPage     = lazy(() => import("@/pages/ClientesPage").then(m => ({ default: m.ClientesPage })));
const RelatoriosPage   = lazy(() => import("@/pages/RelatoriosPage").then(m => ({ default: m.RelatoriosPage })));
const ConfiguracoesPage = lazy(() => import("@/pages/ConfiguracoesPage").then(m => ({ default: m.ConfiguracoesPage })));
const UploadPage        = lazy(() => import("@/pages/UploadPage").then(m => ({ default: m.UploadPage })));
const MatchersPage      = lazy(() => import("@/pages/MatchersPage").then(m => ({ default: m.MatchersPage })));
const GuiasPage         = lazy(() => import("@/pages/GuiasPage").then(m => ({ default: m.GuiasPage })));
const ContratosPage     = lazy(() => import("@/pages/ContratosPage").then(m => ({ default: m.ContratosPage })));
const LaudoPage         = lazy(() => import("@/pages/LaudoPage").then(m => ({ default: m.LaudoPage })));
const ConformidadeFiscalPage = lazy(() => import("@/pages/ConformidadeFiscalPage").then(m => ({ default: m.ConformidadeFiscalPage })));
const GapsFiscaisPage   = lazy(() => import("@/pages/GapsFiscaisPage").then(m => ({ default: m.GapsFiscaisPage })));
const RiscoTributarioPage = lazy(() => import("@/pages/RiscoTributarioPage").then(m => ({ default: m.RiscoTributarioPage })));
const CartasFiscaisPage = lazy(() => import("@/pages/CartasFiscaisPage").then(m => ({ default: m.CartasFiscaisPage })));
const AuditoriaForensePage = lazy(() => import("@/pages/AuditoriaForensePage").then(m => ({ default: m.AuditoriaForensePage })));

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60000, retry: 1 } },
});

const TITULOS: Record<string, string> = {
  dashboard:     "Dashboard",
  conciliacao:   "Análises",
  upload:        "Upload de Extratos",
  matchers:      "Matchers — Conciliação Automática",
  guias:         "Guias Tributárias",
  contratos:     "Contratos Recorrentes",
  clientes:      "Clientes",
  relatorios:    "Histórico de Relatórios",
  configuracoes: "Configurações",
  "conformidade-fiscal": "Conformidade Fiscal",
  "gaps-fiscais":         "Gaps Fiscais",
  "risco-tributario":     "Risco Tributário",
  "cartas-fiscais":       "Cartas de Constatação",
  "auditoria-forense":    "Auditoria Forense",
};

function ProtectedRoute() {
  const { user, loading } = useAuth();
  // DEV: tela de login removida (vamos refazê-la). O gate só vale no build de prod.
  if (import.meta.env.DEV) return <Outlet />;
  if (loading) return <AppBootSkeleton />;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function DashboardLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [dbStatus, setDbStatus] = useState<"online" | "offline" | "checking">("checking");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [sidebarCounts, setSidebarCounts] = useState({ anomalias: 0, clientes: 0 });

  useEffect(() => {
    fetchHealth()
      .then((d) => setDbStatus(d.banco_dados === "ok" ? "online" : "offline"))
      .catch(() => setDbStatus("offline"));

    Promise.all([
      listarConciliacoes().catch(() => []),
      listarClientes().catch(() => []),
    ]).then(([concs, clts]) => {
      const anomalias = Array.isArray(concs)
        ? concs.reduce((s: number, c) => s + (c.total_anomalias ?? 0), 0)
        : 0;
      const clientes = Array.isArray(clts) ? clts.length : 0;
      setSidebarCounts({ anomalias, clientes });
    });
  }, [location.pathname]);

  const secao = location.pathname.replace(/^\//, "");
  const title = TITULOS[secao] ?? "OrgConc";

  return (
    <div className="flex min-h-screen" style={{ background: "var(--d-bg)" }}>
      {/* Desktop sidebar */}
      <Sidebar anomalias={sidebarCounts.anomalias} clientes={sidebarCounts.clientes} />

      {/* Mobile sidebar Sheet */}
      <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
        <SheetContent side="left" className="p-0 w-60 bg-card/95 flex flex-col">
          <SidebarNavContent
            onNavigate={() => setMobileSidebarOpen(false)}
            anomalias={sidebarCounts.anomalias}
            clientes={sidebarCounts.clientes}
          />
        </SheetContent>
      </Sheet>

      <main className="flex-1 flex flex-col min-w-0 relative">
        <Topbar
          title={title}
          dbStatus={dbStatus}
          userEmail={user?.email || user?.sub}
          onLogout={logout}
          onToggleSidebar={() => setMobileSidebarOpen(true)}
        />
        <div className="flex-1 p-4 lg:p-6 xl:p-8 max-w-[1600px] w-full mx-auto pb-16">
          <ErrorBoundary>
            <Suspense fallback={<PageSkeleton />}>
              <Outlet />
            </Suspense>
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter basename="/app">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<DashboardLayout />}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/conciliacao" element={<ConciliacaoPage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/matchers" element={<MatchersPage />} />
                <Route path="/guias" element={<GuiasPage />} />
                <Route path="/contratos" element={<ContratosPage />} />
                <Route path="/laudo" element={<LaudoPage />} />
                <Route path="/conformidade-fiscal" element={<ConformidadeFiscalPage />} />
                <Route path="/gaps-fiscais" element={<GapsFiscaisPage />} />
                <Route path="/risco-tributario" element={<RiscoTributarioPage />} />
                <Route path="/cartas-fiscais" element={<CartasFiscaisPage />} />
                <Route path="/auditoria-forense" element={<AuditoriaForensePage />} />
                <Route path="/clientes" element={<ClientesPage />} />
                <Route path="/relatorios" element={<RelatoriosPage />} />
                <Route path="/configuracoes" element={<ConfiguracoesPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <Toaster richColors position="top-right" />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
    </QueryClientProvider>
  );
}
