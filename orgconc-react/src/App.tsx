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
import { Sidebar, SidebarNavContent } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { Toaster } from "@/components/ui/sonner";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { ErrorBoundary } from "@/components/ErrorBoundary";

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
        <div className="flex-1 p-4 lg:p-10 xl:p-12 max-w-[1400px] w-full mx-auto pb-24">
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
