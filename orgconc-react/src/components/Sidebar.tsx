import { useNavigate, useLocation } from "react-router-dom";
import { Logo } from "@/components/Logo";
import {
  Users,
  FileText,
  Code2,
  HeartPulse,
  LayoutDashboard,
  LineChart,
  Settings,
  AlertTriangle,
  ArrowLeftRight,
  ShieldCheck,
  Activity,
  Lock,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Secao =
  | "dashboard"
  | "conciliacao"
  | "clientes"
  | "relatorios"
  | "anomalias"
  | "transacoes"
  | "auditoria"
  | "seguranca"
  | "configuracoes";

interface NavItemDef {
  id: Secao;
  label: string;
  icon: typeof LineChart;
  badge?: string;
}

const OPERACAO_ITEMS: NavItemDef[] = [
  { id: "dashboard",   label: "Dashboard",    icon: LayoutDashboard },
  { id: "conciliacao", label: "Conciliação",  icon: LineChart },
  { id: "clientes",    label: "Clientes",     icon: Users },
  { id: "relatorios",  label: "Relatórios",   icon: FileText },
  { id: "transacoes",  label: "Transações",   icon: ArrowLeftRight },
  { id: "anomalias",   label: "Anomalias",    icon: AlertTriangle },
];

const COMPLIANCE_ITEMS: NavItemDef[] = [
  { id: "auditoria",     label: "Auditoria",     icon: Activity },
  { id: "seguranca",     label: "Segurança",     icon: ShieldCheck },
  { id: "configuracoes", label: "Configurações", icon: Settings },
];

interface SidebarCounts {
  anomalias?: number;
  clientes?: number;
}

export function SidebarNavContent({
  onNavigate,
  counts,
}: {
  onNavigate?: () => void;
  counts?: SidebarCounts;
}) {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  function go(id: string) {
    navigate(`/${id}`);
    onNavigate?.();
  }

  function isActive(id: string) {
    return pathname === `/${id}` || (id === "dashboard" && pathname === "/");
  }

  function getBadge(id: Secao): string | undefined {
    if (id === "anomalias" && counts?.anomalias) return String(counts.anomalias);
    if (id === "clientes" && counts?.clientes) return String(counts.clientes);
    return undefined;
  }

  return (
    <>
      <div className="flex items-center gap-3 px-5 py-5 border-b">
        <Logo size={56} />
        <div className="flex flex-col">
          <h1
            className="font-bold text-lg tracking-tight text-foreground leading-tight"
            style={{ letterSpacing: "-0.025em" }}
          >
            ORGATEC
          </h1>
          <span className="text-[10px] font-semibold tracking-[0.18em] uppercase text-muted-foreground mt-0.5 font-mono">
            Conciliação Bancária
          </span>
        </div>
      </div>

      <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto" aria-label="Navegação principal">
        <NavGroup label="Operação">
          {OPERACAO_ITEMS.map(({ id, label, icon: Icon }) => (
            <NavItem
              key={id}
              active={isActive(id)}
              onClick={() => go(id)}
              icon={<Icon className="h-4 w-4" />}
              label={label}
              badge={getBadge(id)}
              badgeVariant={id === "anomalias" ? "warning" : "info"}
            />
          ))}
        </NavGroup>

        <NavGroup label="Compliance">
          {COMPLIANCE_ITEMS.map(({ id, label, icon: Icon }) => (
            <NavItem
              key={id}
              active={isActive(id)}
              onClick={() => go(id)}
              icon={<Icon className="h-4 w-4" />}
              label={label}
            />
          ))}
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

      <SecurityCard />

      <div className="border-t px-4 py-3">
        <div className="inline-flex items-center rounded-md border bg-secondary px-2 py-1 text-[11px] font-mono font-semibold text-muted-foreground">
          v0.5.0
        </div>
      </div>
    </>
  );
}

export function Sidebar({ counts }: { counts?: SidebarCounts }) {
  return (
    <aside className="hidden lg:flex w-60 shrink-0 flex-col bg-card/95 backdrop-blur-sm relative">
      <span aria-hidden className="absolute top-0 bottom-0 right-0 w-px coastline-r opacity-60" />
      <SidebarNavContent counts={counts} />
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
  badge,
  badgeVariant = "info",
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: string;
  badgeVariant?: "info" | "warning";
}) {
  const badgeCls = active
    ? "bg-primary/20 text-primary"
    : badgeVariant === "warning"
    ? "bg-orange-100 text-orange-600 dark:bg-orange-950/50 dark:text-orange-400"
    : "bg-blue-100 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400";

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
      <span className="flex-1 text-left">{label}</span>
      {badge && (
        <span className={cn("ml-auto inline-flex items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-bold font-mono min-w-[18px]", badgeCls)}>
          {badge}
        </span>
      )}
    </button>
  );
}

function SecurityCard() {
  return (
    <div className="mx-3 mb-3 rounded-xl border bg-gradient-to-br from-primary/5 to-accent/5 p-3">
      <div className="flex items-center gap-2 mb-1.5">
        <div className="rounded-md bg-primary/10 p-1.5 text-primary">
          <Lock className="h-3.5 w-3.5" />
        </div>
        <span className="text-xs font-semibold text-foreground">Criptografia Ativa</span>
      </div>
      <p className="text-[11px] leading-snug text-muted-foreground">
        Dados protegidos com AES-256 e TLS 1.3 ponta a ponta.
      </p>
    </div>
  );
}
