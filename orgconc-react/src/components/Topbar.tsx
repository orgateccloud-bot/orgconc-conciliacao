import { Logo } from "@/components/Logo";
import { useTheme } from "@/lib/theme";
import { Moon, Sun, Menu } from "lucide-react";
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

  const dbPill = {
    online:   "trust-pill-up",
    offline:  "trust-pill-crit",
    checking: "bg-muted text-muted-foreground",
  }[dbStatus];

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between bg-card/85 backdrop-blur-md px-4 lg:px-6 relative">
      {/* Linha de costa: hairline gradient navy → cyan (borda inferior) */}
      <span aria-hidden className="absolute left-0 right-0 bottom-0 h-px coastline-b opacity-60" />
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="lg:hidden p-1.5 rounded-md hover:bg-secondary"
            aria-label="Abrir menu"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <Logo size={32} />
        <h2 className="text-lg font-light tracking-tight text-foreground">{title}</h2>
      </div>

      <div className="flex items-center gap-2">
        <span className={`trust-pill ${dbPill}`}>
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              dbStatus === "online" ? "bg-success" : dbStatus === "offline" ? "bg-danger" : "bg-muted-foreground"
            }`}
          />
          DB: {dbStatus}
        </span>

        {userEmail && (
          <span className="hidden sm:inline text-xs text-muted-foreground truncate max-w-[140px]">
            {userEmail}
          </span>
        )}
        {onLogout && (
          <Button size="sm" variant="ghost" onClick={onLogout}>
            Sair
          </Button>
        )}
        <Button
          size="icon"
          variant="outline"
          onClick={toggle}
          aria-label={tema === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}
          className="h-9 w-9"
        >
          {tema === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}
