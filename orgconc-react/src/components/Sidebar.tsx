import { Logo } from "@/components/Logo";
import { LayoutDashboard, Users, FileText, Code2, HeartPulse } from "lucide-react";
import { cn } from "@/lib/utils";

export type Secao = "conciliacao" | "clientes" | "relatorios";

const ITEMS: Array<{ id: Secao; label: string; icon: typeof LayoutDashboard }> = [
  { id: "conciliacao", label: "Conciliação", icon: LayoutDashboard },
  { id: "clientes",    label: "Clientes",    icon: Users },
  { id: "relatorios",  label: "Relatórios",  icon: FileText },
];

interface Props {
  secao: Secao;
  onChange: (s: Secao) => void;
}

export function Sidebar({ secao, onChange }: Props) {
  return (
    <aside className="hidden lg:flex w-60 shrink-0 flex-col bg-card/95 backdrop-blur-sm relative">
      {/* Linha de costa: hairline gradient navy → cyan */}
      <span aria-hidden className="absolute top-0 bottom-0 right-0 w-px coastline-r opacity-60" />
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5 border-b">
        <Logo size={56} />
        <div className="flex flex-col">
          <h1 className="font-bold text-lg tracking-tight text-foreground leading-tight" style={{ letterSpacing: "-0.025em" }}>ORGATEC</h1>
          <span className="text-[10px] font-semibold tracking-[0.18em] uppercase text-muted-foreground mt-0.5 font-mono">
            Conciliação Bancária
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-0.5" aria-label="Navegação principal">
        <NavGroup label="Principal">
          {ITEMS.map(({ id, label, icon: Icon }) => (
            <NavItem
              key={id}
              active={secao === id}
              onClick={() => onChange(id)}
              icon={<Icon className="h-4 w-4" />}
              label={label}
            />
          ))}
        </NavGroup>

        <NavGroup label="Suporte">
          <a
            href="/docs"
            target="_blank"
            rel="noopener"
            className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
          >
            <Code2 className="h-4 w-4" />
            API Docs
          </a>
          <a
            href="/health"
            target="_blank"
            rel="noopener"
            className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
          >
            <HeartPulse className="h-4 w-4" />
            Health Check
          </a>
        </NavGroup>
      </nav>

      {/* Footer */}
      <div className="border-t px-4 py-3">
        <div className="inline-flex items-center rounded-md border bg-secondary px-2 py-1 text-[11px] font-mono font-semibold text-muted-foreground">
          v0.5.0
        </div>
      </div>
    </aside>
  );
}

function NavGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="pt-2 first:pt-0">
      <div className="px-3 pb-1 pt-2 text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function NavItem({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "w-full flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
        active
          ? "bg-primary/10 text-primary font-semibold shadow-[inset_2px_0_0_hsl(var(--primary))]"
          : "text-muted-foreground hover:bg-secondary hover:text-foreground"
      )}
    >
      {icon}
      {label}
    </button>
  );
}
