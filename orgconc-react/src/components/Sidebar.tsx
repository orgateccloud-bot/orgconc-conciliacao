import { useNavigate, useLocation } from "react-router-dom";
import { Logo } from "@/components/Logo";
import {
  Users, FileText, LayoutDashboard, LineChart, Settings,
  Upload, AlertTriangle, ShieldCheck, Lock, Activity,
  Network, Receipt, FileSignature, ScrollText, FileWarning, Calculator, Gauge,
  FileBarChart2, UserCog,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type SidebarItem = {
  id: string;
  label: string;
  icon: typeof LineChart;
  badge?: number;
  href?: string;
};

const OPERACAO_ITEMS: SidebarItem[] = [
  { id: "dashboard",   label: "Visão Geral",  icon: LayoutDashboard },
  { id: "upload",      label: "Upload",       icon: Upload },
  { id: "conciliacao", label: "Análises",     icon: LineChart },
  { id: "matchers",    label: "Matchers",     icon: Network },
  { id: "guias",       label: "Guias",        icon: Receipt },
  { id: "contratos",   label: "Contratos",    icon: FileSignature },
  { id: "relatorios",  label: "Transações",   icon: Activity },
  { id: "clientes",    label: "Clientes",     icon: Users },
  { id: "anomalias",   label: "Anomalias",    icon: AlertTriangle },
];

const FISCAL_ITEMS: SidebarItem[] = [
  { id: "laudo",               label: "Laudo Integrado",   icon: FileBarChart2 },
  { id: "conformidade-fiscal", label: "Conformidade",      icon: ScrollText },
  { id: "gaps-fiscais",        label: "Gaps Fiscais",      icon: FileWarning },
  { id: "risco-tributario",    label: "Risco Tributário",  icon: Calculator },
  { id: "auditoria-forense",   label: "Auditoria Forense", icon: Gauge },
  { id: "cartas-fiscais",      label: "Cartas",            icon: FileText },
];

const COMPLIANCE_ITEMS: SidebarItem[] = [
  { id: "auditoria",   label: "Auditoria",    icon: ShieldCheck },
  { id: "seguranca",   label: "Segurança",    icon: Lock },
  { id: "usuarios",    label: "Usuários",     icon: UserCog },
  { id: "configuracoes", label: "Configurações", icon: Settings },
];

export function SidebarNavContent({
  onNavigate,
  anomalias = 0,
  clientes = 0,
}: {
  onNavigate?: () => void;
  anomalias?: number;
  clientes?: number;
}) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { user } = useAuth();

  // "Usuários" (gestão de acessos) só para admin.
  const complianceItems =
    user?.role === "admin"
      ? COMPLIANCE_ITEMS
      : COMPLIANCE_ITEMS.filter((i) => i.id !== "usuarios");

  const operacaoWithBadges = OPERACAO_ITEMS.map((item) => ({
    ...item,
    badge:
      item.id === "clientes" && clientes > 0
        ? clientes
        : item.id === "anomalias" && anomalias > 0
        ? anomalias
        : undefined,
  }));

  function go(id: string) {
    const routableIds = [
      "dashboard","conciliacao","upload","matchers","guias","contratos",
      "clientes","usuarios","anomalias","relatorios","configuracoes",
      "conformidade-fiscal","gaps-fiscais","risco-tributario","cartas-fiscais",
      "laudo",
      "auditoria-forense",
    ];
    if (routableIds.includes(id)) navigate(`/${id}`);
    onNavigate?.();
  }

  function isActive(id: string, label: string) {
    if (label === "Transações") return pathname === "/relatorios";
    return pathname === `/${id}` || (id === "dashboard" && (pathname === "/" || pathname === "/dashboard"));
  }

  return (
    <>
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b">
        <Logo size={52} />
        <div className="flex flex-col">
          <h1 className="font-bold text-lg tracking-tight leading-tight" style={{ letterSpacing: "-0.025em" }}>
            ORGATEC
          </h1>
          <span className="text-[10px] font-semibold tracking-[0.18em] uppercase text-muted-foreground mt-0.5 font-mono">
            Conciliação Bancária
          </span>
        </div>
      </div>

      <nav className="flex-1 px-2 py-4 overflow-y-auto" aria-label="Navegação principal">
        {/* OPERAÇÃO */}
        <NavGroup label="Operação">
          {operacaoWithBadges.map((item) => (
            <NavItem
              key={item.label}
              active={isActive(item.id, item.label)}
              onClick={() => go(item.id)}
              icon={<item.icon className="h-4 w-4" />}
              label={item.label}
              badge={item.badge}
            />
          ))}
        </NavGroup>

        {/* FISCAL */}
        <NavGroup label="Fiscal">
          {FISCAL_ITEMS.map((item) => (
            <NavItem
              key={item.id}
              active={isActive(item.id, item.label)}
              onClick={() => go(item.id)}
              icon={<item.icon className="h-4 w-4" />}
              label={item.label}
            />
          ))}
        </NavGroup>

        {/* COMPLIANCE */}
        <NavGroup label="Compliance">
          {complianceItems.map((item) => (
            <NavItem
              key={item.id}
              active={isActive(item.id, item.label)}
              onClick={() => go(item.id)}
              icon={<item.icon className="h-4 w-4" />}
              label={item.label}
            />
          ))}
        </NavGroup>
      </nav>

      {/* Criptografia Ativa card */}
      <div className="px-3 py-3 border-t">
        <div className="rounded-xl bg-primary/10 border border-primary/20 px-3 py-2.5 flex items-start gap-2.5">
          <div className="mt-0.5 shrink-0 rounded-lg bg-primary/20 p-1">
            <Lock className="h-3 w-3 text-primary" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-primary">Criptografia Ativa</p>
            <p className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
              Todos os dados protegidos com AES-256 e TLS 1.3
            </p>
          </div>
        </div>
        <div className="mt-2 px-1">
          <span className="inline-flex items-center rounded-md border bg-secondary px-2 py-0.5 text-[10px] font-mono font-semibold text-muted-foreground">
            v0.5.0
          </span>
        </div>
      </div>
    </>
  );
}

export function Sidebar({
  anomalias,
  clientes,
}: {
  anomalias?: number;
  clientes?: number;
}) {
  return (
    <aside className="hidden lg:flex w-60 shrink-0 flex-col bg-card/95 backdrop-blur-xs relative">
      <span aria-hidden className="absolute top-0 bottom-0 right-0 w-px coastline-r opacity-60" />
      <SidebarNavContent anomalias={anomalias} clientes={clientes} />
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
  active, onClick, icon, label, badge,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: number;
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
      <span className="flex-1 text-left">{label}</span>
      {badge !== undefined && (
        <span className={cn(
          "inline-flex items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-bold min-w-[18px]",
          active
            ? "bg-primary/20 text-primary"
            : label === "Anomalias"
            ? "bg-orange-100 text-orange-600 dark:bg-orange-950/50 dark:text-orange-400"
            : "bg-blue-100 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400"
        )}>
          {badge}
        </span>
      )}
    </button>
  );
}
