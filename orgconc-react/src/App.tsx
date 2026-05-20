import { useEffect, useState } from "react";
import { ThemeProvider } from "@/lib/theme";
import { Sidebar, type Secao } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { Toaster } from "@/components/ui/sonner";
import { HeroCard } from "@/components/HeroCard";
import { PaletteStrip } from "@/components/PaletteStrip";

interface Tela {
  eyebrow: string;
  title: string;
  accent: string;
  subtitle: string;
}

const TELAS: Record<Secao, Tela> = {
  conciliacao: {
    eyebrow: "01 · NOVA CARTA DE CONCILIAÇÃO",
    title: "Contabilidade que",
    accent: "respira.",
    subtitle:
      "Carregue extratos OFX, PDF ou XML e cruze profundidades contábeis com sondagem assistida por Claude — relatórios em HTML, Excel e PDF.",
  },
  clientes: {
    eyebrow: "02 · CADASTRO FISCAL",
    title: "Clientes",
    accent: "ativos.",
    subtitle: "Carteira de empresas atendidas com plano, CNPJ e histórico de conciliações.",
  },
  relatorios: {
    eyebrow: "03 · ARQUIVOS DE BORDO",
    title: "Histórico de",
    accent: "relatórios.",
    subtitle:
      "Cartas batimétricas geradas — consulte conciliações anteriores e exporte em HTML, Excel ou PDF.",
  },
};

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

  const tela = TELAS[secao];

  return (
    <ThemeProvider>
      <div className="flex min-h-screen" style={{ background: "var(--d-bg)" }}>
        <Sidebar secao={secao} onChange={setSecao} />
        <main className="flex-1 flex flex-col min-w-0 relative">
          <Topbar title={TITULOS[secao]} dbStatus={dbStatus} />
          <div className="flex-1 p-4 lg:p-10 xl:p-12 space-y-10 max-w-[1400px] w-full mx-auto pb-24">
            <HeroCard
              eyebrow={tela.eyebrow}
              title={tela.title}
              titleAccent={tela.accent}
              subtitle={tela.subtitle}
            />
            <PaletteStrip />
            <SprintCard />
          </div>
          <SlideFooter section={secao} />
        </main>
        <Toaster richColors position="top-right" />
      </div>
    </ThemeProvider>
  );
}

function SprintCard() {
  return (
    <section className="animate-fade-in">
      <header className="flex items-baseline justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="eyebrow">Diário de bordo</h2>
          <span className="h-px w-12 bg-border" />
        </div>
        <span className="deck-caption">Sprint 01 · Concluído</span>
      </header>

      <div className="rounded-3xl border bg-card p-7 lg:p-10">
        <h3 className="font-semibold text-2xl tracking-tight text-foreground mb-5">
          Sondagem de fundação — Sprint I
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-10 gap-y-3 text-sm text-foreground">
          <Item label="Arquitetura" valor="React 18 · TypeScript · Vite" />
          <Item label="Sistema" valor="Tailwind 3.4 · shadcn/ui · 43 componentes" />
          <Item label="Tipografia" valor="Manrope 200 · Instrument Serif italic · JetBrains Mono" />
          <Item label="Paleta" valor="Direção Leve · navy → blue → azure" />
          <Item label="Tema" valor="Light & dark · persistência localStorage" />
          <Item label="Responsividade" valor="≥ 1024 px com sidebar fixa" />
        </div>

        <footer className="mt-7 pt-5 border-t border-border flex items-baseline justify-between">
          <span className="deck-caption">Próxima carta</span>
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
    <div className="flex items-baseline gap-3 py-1.5">
      <span className="eyebrow shrink-0 w-[120px] text-[0.7rem]">{label}</span>
      <span className="h-px flex-1 bg-border/60 self-center" />
      <span className="text-foreground/90 text-sm">{valor}</span>
    </div>
  );
}

function SlideFooter({ section }: { section: Secao }) {
  return (
    <footer
      aria-hidden
      className="absolute bottom-4 left-4 right-4 lg:left-10 lg:right-10 flex items-center justify-between"
    >
      <span className="deck-caption opacity-60">orgatec · {section}</span>
      <span className="deck-caption opacity-60">v0.5.0</span>
    </footer>
  );
}
