import { Logo } from "@/components/Logo";
import { useTheme } from "@/lib/theme";
import { Moon, Sun, Menu, Bell, Search } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  title: string;
  dbStatus: "online" | "offline" | "checking";
  onToggleSidebar?: () => void;
  userEmail?: string;
  onLogout?: () => void;
}

export function Topbar({ title, dbStatus, onToggleSidebar, userEmail, onLogout }: Props) {
  const { tema, toggle } = useTheme();

  const initials = userEmail
    ? userEmail.slice(0, 2).toUpperCase()
    : "JD";

  const dbLabel = dbStatus === "online" ? "conectado" : dbStatus === "offline" ? "offline" : "conectando...";
  const dbColor = {
    online:   "bg-green-50 text-green-700 border-green-200 dark:bg-green-950/30 dark:text-green-400 dark:border-green-800",
    offline:  "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/30 dark:text-red-400",
    checking: "bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950/30 dark:text-yellow-400",
  }[dbStatus];

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between bg-card/90 backdrop-blur-md px-4 lg:px-6 gap-3 relative">
      <span aria-hidden className="absolute left-0 right-0 bottom-0 h-px coastline-b opacity-60" />

      {/* Left: hamburger + logo + title */}
      <div className="flex items-center gap-3 shrink-0">
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="lg:hidden p-1.5 rounded-md hover:bg-secondary"
            aria-label="Abrir menu"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <Logo size={28} />
        <h2 className="text-base font-semibold tracking-tight hidden sm:block">{title}</h2>
      </div>

      {/* Center: search bar */}
      <div className="hidden md:flex flex-1 max-w-md">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Buscar transações, contas, anomalias..."
            className="w-full h-8 rounded-lg border bg-secondary/60 pl-9 pr-14 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            readOnly
          />
          <kbd className="absolute right-2 top-1/2 -translate-y-1/2 hidden lg:inline-flex items-center gap-0.5 rounded border bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
            ⌘K
          </kbd>
        </div>
      </div>

      {/* Right: badges + actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* DB status */}
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold font-mono ${dbColor}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${
            dbStatus === "online" ? "bg-green-500" : dbStatus === "offline" ? "bg-red-500" : "bg-yellow-500 animate-pulse"
          }`} />
          {dbLabel}
        </span>

        {/* Bell */}
        <button
          aria-label="Notificações"
          disabled
          title="Em breve"
          className="relative p-1.5 rounded-md hover:bg-secondary text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Bell className="h-4 w-4" />
        </button>

        {/* Theme */}
        <Button
          size="icon"
          variant="ghost"
          onClick={toggle}
          aria-label={tema === "dark" ? "Tema claro" : "Tema escuro"}
          className="h-8 w-8"
        >
          {tema === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>

        {/* User avatar */}
        {userEmail && (
          <button
            onClick={onLogout}
            title={`${userEmail} — clique para sair`}
            className="h-8 w-8 rounded-full bg-primary text-primary-foreground text-[11px] font-bold flex items-center justify-center hover:opacity-90 transition-opacity"
          >
            {initials}
          </button>
        )}
      </div>
    </header>
  );
}
