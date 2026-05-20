import { useEffect, useState } from "react";
import { ThemeProvider } from "@/lib/theme";
import { Sidebar, type Secao } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { Toaster } from "@/components/ui/sonner";
import { Logo } from "@/components/Logo";

const TITULOS: Record<Secao, string> = {
  conciliacao: "Conciliação Bancária",
  clientes: "Clientes",
  relatorios: "Histórico de Relatórios",
};

export default function App() {
  const [secao, setSecao] = useState<Secao>("conciliacao");
  const [dbStatus, setDbStatus] = useState<"online" | "offline" | "checking">("checking");

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((d) => setDbStatus(d.banco_dados === "ok" ? "online" : "offline"))
      .catch(() => setDbStatus("offline"));
  }, []);

  return (
    <ThemeProvider>
      <div className="flex min-h-screen bg-background">
        <Sidebar secao={secao} onChange={setSecao} />
        <main className="flex-1 flex flex-col min-w-0">
          <Topbar title={TITULOS[secao]} dbStatus={dbStatus} />
          <div className="flex-1 p-4 lg:p-8">
            <Placeholder secao={secao} />
          </div>
        </main>
        <Toaster richColors position="top-right" />
      </div>
    </ThemeProvider>
  );
}

function Placeholder({ secao }: { secao: Secao }) {
  return (
    <div className="animate-fade-in max-w-6xl">
      <div className="mb-8 flex items-center gap-4">
        <div className="h-16 w-16 rounded-2xl bg-brand-gradient p-3 shadow-lg flex items-center justify-center">
          <Logo size={44} />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{TITULOS[secao]}</h1>
          <p className="text-sm text-muted-foreground">
            Dashboard ORGATEC · v0.5.0 (React + shadcn/ui)
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3 mb-6">
        <BrandStripeCard label="Navy" color="#1E3A8A" />
        <BrandStripeCard label="Blue" color="#2563EB" />
        <BrandStripeCard label="Cyan" color="#22D3EE" />
      </div>

      <div className="rounded-lg border bg-card p-6 shadow-card">
        <h3 className="text-xs font-bold mb-3 text-muted-foreground tracking-[0.12em] uppercase">
          Sprint 1 — Setup + Design System + Shell
        </h3>
        <ul className="text-sm space-y-2 text-foreground">
          <li className="flex items-center gap-2">✓ React 18 + TypeScript + Vite</li>
          <li className="flex items-center gap-2">
            ✓ Tailwind 3.4 com paleta extraída do logo (navy → blue → cyan)
          </li>
          <li className="flex items-center gap-2">✓ shadcn/ui (43 componentes pré-instalados)</li>
          <li className="flex items-center gap-2">
            ✓ ThemeProvider (light/dark) com persistência localStorage
          </li>
          <li className="flex items-center gap-2">
            ✓ Tipografia Inter + JetBrains Mono carregadas via Google Fonts
          </li>
          <li className="flex items-center gap-2">
            ✓ Layout responsivo (sidebar oculta em &lt;1024px)
          </li>
        </ul>
        <p className="mt-4 text-xs text-muted-foreground">
          Próximo: Sprint 2 — Tela de Conciliação (Steps, Mode Cards, Upload Zone, File List).
        </p>
      </div>
    </div>
  );
}

function BrandStripeCard({ label, color }: { label: string; color: string }) {
  return (
    <div className="rounded-lg border bg-card shadow-card overflow-hidden">
      <div className="h-16" style={{ background: color }} />
      <div className="p-3 flex items-center justify-between">
        <span className="text-sm font-semibold">{label}</span>
        <span className="text-xs font-mono text-muted-foreground">{color}</span>
      </div>
    </div>
  );
}
