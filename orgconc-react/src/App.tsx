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
import { LoginPage } from "@/pages/LoginPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { Sidebar, SidebarNavContent } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { Toaster } from "@/components/ui/sonner";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import {
  AlertTriangle,
  ArrowLeftRight,
  ShieldCheck,
  Activity,
} from "lucide-react";

const DashboardPage    = lazy(() => import("@/pages/DashboardPage").then(m => ({ default: m.DashboardPage })));
const ConciliacaoPage  = lazy(() => import("@/pages/ConciliacaoPage").then(m => ({ default: m.ConciliacaoPage })));
const ClientesPage     = lazy(() => import("@/pages/ClientesPage").then(m => ({ default: m.ClientesPage })));
const RelatoriosPage   = lazy(() => import("@/pages/RelatoriosPage").then(m => ({ default: m.RelatoriosPage })));
const ConfiguracoesPage = lazy(() => import("@/pages/ConfiguracoesPage").then(m => ({ default: m.ConfiguracoesPage })));

function PageLoader() {
  return (
    <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
      Carregando…
    </div>
  );
}

const TITULOS: Record<string, string> = {
  dashboard:     "Dashboard",
  conciliacao:   "Conciliação Bancária",
  clientes:      "Clientes",
  relatorios:    "Histórico de Relatórios",
  configuracoes: "Configurações",
  anomalias:     "Anomalias",
  transacoes:    "Transações",
  auditoria:     "Trilha de Auditoria",
  seguranca:     "Segurança",
};

function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Carregando…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function DashboardLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [dbStatus, setDbStatus] = useState<"online" | "offline" | "checking">("checking");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((d) => setDbStatus(d.banco_dados === "ok" ? "online" : "offline"))
      .catch(() => setDbStatus("offline"));
  }, []);

  const secao = location.pathname.replace(/^\//, "");
  const title = TITULOS[secao] ?? "OrgConc";

  return (
    <div className="flex min-h-screen" style={{ background: "var(--d-bg)" }}>
      {/* Desktop sidebar */}
      <Sidebar />

      {/* Mobile sidebar Sheet */}
      <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
        <SheetContent side="left" className="p-0 w-60 bg-card/95 flex flex-col">
          <SidebarNavContent onNavigate={() => setMobileSidebarOpen(false)} />
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
        <div className="flex-1 p-4 lg:p-8 xl:p-10 max-w-[1600px] w-full mx-auto pb-24">
          <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
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
                <Route path="/clientes" element={<ClientesPage />} />
                <Route path="/relatorios" element={<RelatoriosPage />} />
                <Route path="/configuracoes" element={<ConfiguracoesPage />} />
                <Route
                  path="/transacoes"
                  element={
                    <PlaceholderPage
                      titulo="Transações"
                      descricao="Visão consolidada de todas as transações cruzando conciliações. Filtros por banco, conta, categoria e período em desenvolvimento."
                      icone={ArrowLeftRight}
                    />
                  }
                />
                <Route
                  path="/anomalias"
                  element={
                    <PlaceholderPage
                      titulo="Anomalias"
                      descricao="Catálogo centralizado de anomalias detectadas pela IA — duplicidades, valores atípicos, padrões suspeitos. Triagem e investigação em desenvolvimento."
                      icone={AlertTriangle}
                    />
                  }
                />
                <Route
                  path="/auditoria"
                  element={
                    <PlaceholderPage
                      titulo="Trilha de Auditoria"
                      descricao="Histórico imutável de eventos com hash chain (sha256 + prev_hash). Verificação de integridade e exportação para compliance em desenvolvimento."
                      icone={Activity}
                    />
                  }
                />
                <Route
                  path="/seguranca"
                  element={
                    <PlaceholderPage
                      titulo="Segurança"
                      descricao="Score de compliance, controles ativos, certificações e logs de acesso. Painel completo em desenvolvimento."
                      icone={ShieldCheck}
                    />
                  }
                />
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
