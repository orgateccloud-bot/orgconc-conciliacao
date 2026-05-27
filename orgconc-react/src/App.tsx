import { lazy, Suspense, useEffect, useState } from "react";
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
import { listarClientes, listarConciliacoes } from "@/lib/api";
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
};

function ProtectedRoute() {
  const { user, loading } = useAuth();
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
    fetch("/health")
      .then((r) => r.json())
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
  }, []);

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
  );
}
