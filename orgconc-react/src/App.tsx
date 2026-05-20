import { useEffect, useState } from "react";
import { ThemeProvider } from "@/lib/theme";
import { Sidebar, type Secao } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { Toaster } from "@/components/ui/sonner";
import { BathymetricBackground } from "@/components/BathymetricBackground";
import { HeroCard } from "@/components/HeroCard";
import { PaletteStrip } from "@/components/PaletteStrip";
import { Compass } from "@/components/Compass";

const TITULOS: Record<Secao, string> = {
  conciliacao: "Conciliação Bancária",
  clientes: "Clientes",
  relatorios: "Histórico de Relatórios",
};

const SUBTITULOS: Record<Secao, string> = {
  conciliacao:
    "Atlas de fluxos financeiros — cruze extratos OFX, PDF e XML; mapeie as profundidades contábeis com sondagem assistida por IA.",
  clientes:
    "Cadastro fiscal dos pavilhões atendidos pelo escritório.",
  relatorios:
    "Cartas batimétricas geradas — consulte conciliações anteriores e exporte em HTML, Excel ou PDF.",
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
      <div className="flex min-h-screen bg-background relative">
        <BathymetricBackground />
        <Sidebar secao={secao} onChange={setSecao} />
        <main className="flex-1 flex flex-col min-w-0 relative">
          <Topbar title={TITULOS[secao]} dbStatus={dbStatus} />
          <div className="flex-1 p-4 lg:p-8 xl:p-10 space-y-8 max-w-[1400px] w-full mx-auto">
            <HeroCard
              title={TITULOS[secao]}
              subtitle={SUBTITULOS[secao]}
            />
            <PaletteStrip />
            <SprintCard />
          </div>
        </main>
        <Toaster richColors position="top-right" />
      </div>
    </ThemeProvider>
  );
}

function SprintCard() {
  return (
    <section className="relative animate-fade-in">
      <header className="flex items-baseline justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="atlas-label">Diário de bordo</h2>
          <span className="h-px w-12 bg-border" />
        </div>
        <span className="atlas-caption">Sprint 01 · Concluído</span>
      </header>

      <div className="relative overflow-hidden rounded-lg border bg-card shadow-card p-6 lg:p-8">
        {/* Rosa-dos-ventos decorativa no canto */}
        <Compass size={36} className="absolute top-5 right-5 opacity-50" />

        <h3 className="font-semibold text-foreground tracking-tight mb-4 pr-12">
          Sondagem de fundação — Sprint I
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2.5 text-sm text-foreground">
          <Item label="Arquitetura" valor="React 18 · TypeScript · Vite" />
          <Item label="Sistema" valor="Tailwind 3.4 · shadcn/ui · 43 componentes" />
          <Item label="Paleta" valor="3 zonas batimétricas · navy → blue → cyan" />
          <Item label="Tipografia" valor="Inter (corpo) · JetBrains Mono (medições)" />
          <Item label="Tema" valor="Light & dark · persistência localStorage" />
          <Item label="Responsividade" valor="≥ 1024 px com sidebar fixa" />
        </div>

        <footer className="mt-6 pt-4 border-t flex items-baseline justify-between">
          <span className="atlas-caption">Próxima carta</span>
          <span className="text-xs text-foreground/80">
            Sprint II — Mapa de modos & rotina de upload
          </span>
        </footer>
      </div>
    </section>
  );
}

function Item({ label, valor }: { label: string; valor: string }) {
  return (
    <div className="flex items-baseline gap-3 py-1">
      <span className="atlas-label shrink-0 w-[110px]">{label}</span>
      <span className="h-px flex-1 bg-border/60 self-center" />
      <span className="text-foreground/90">{valor}</span>
    </div>
  );
}
