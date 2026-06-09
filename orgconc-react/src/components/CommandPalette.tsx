import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

interface Destino {
  label: string;
  path: string;
  grupo: string;
  adminOnly?: boolean;
}

// Apenas destinos com rota REAL (ver App.tsx) — nada de entradas mortas.
const DESTINOS: Destino[] = [
  { label: "Visão Geral", path: "/dashboard", grupo: "Operação" },
  { label: "Upload de Extratos", path: "/upload", grupo: "Operação" },
  { label: "Análises", path: "/conciliacao", grupo: "Operação" },
  { label: "Matchers", path: "/matchers", grupo: "Operação" },
  { label: "Guias Tributárias", path: "/guias", grupo: "Operação" },
  { label: "Contratos", path: "/contratos", grupo: "Operação" },
  { label: "Transações", path: "/relatorios", grupo: "Operação" },
  { label: "Clientes", path: "/clientes", grupo: "Operação" },
  { label: "Laudo Integrado", path: "/laudo", grupo: "Fiscal" },
  { label: "Conformidade Fiscal", path: "/conformidade-fiscal", grupo: "Fiscal" },
  { label: "Gaps Fiscais", path: "/gaps-fiscais", grupo: "Fiscal" },
  { label: "Risco Tributário", path: "/risco-tributario", grupo: "Fiscal" },
  { label: "Auditoria Forense", path: "/auditoria-forense", grupo: "Fiscal" },
  { label: "Cartas de Constatação", path: "/cartas-fiscais", grupo: "Fiscal" },
  { label: "Usuários & Organizações", path: "/usuarios", grupo: "Compliance", adminOnly: true },
  { label: "Configurações", path: "/configuracoes", grupo: "Compliance" },
];

/**
 * Command palette de navegação (⌘K). Sem backend: pula para as telas do app.
 * Substitui a antiga busca morta da Topbar.
 */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const destinos = useMemo(
    () => DESTINOS.filter((d) => !d.adminOnly || user?.role === "admin"),
    [user?.role],
  );

  const filtrados = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return destinos;
    return destinos.filter((d) => `${d.label} ${d.grupo}`.toLowerCase().includes(t));
  }, [q, destinos]);

  useEffect(() => {
    if (open) {
      setQ("");
      setSel(0);
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
  }, [open]);

  useEffect(() => {
    setSel(0);
  }, [q]);

  if (!open) return null;

  function escolher(d: Destino) {
    navigate(d.path);
    onClose();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSel((s) => Math.min(s + 1, filtrados.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSel((s) => Math.max(s - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtrados[sel]) escolher(filtrados[sel]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 backdrop-blur-xs pt-[15vh]"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="mx-4 w-full max-w-lg overflow-hidden rounded-2xl border bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Buscar e navegar"
      >
        <div className="flex items-center gap-2 border-b px-4">
          <Search className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ir para…"
            aria-label="Buscar telas"
            className="h-12 w-full bg-transparent text-sm placeholder:text-muted-foreground focus:outline-hidden"
          />
          <kbd className="hidden sm:inline-flex items-center rounded border bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
            esc
          </kbd>
        </div>
        <ul className="max-h-[50vh] overflow-y-auto p-2" role="listbox" aria-label="Telas">
          {filtrados.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted-foreground">Nada encontrado</li>
          )}
          {filtrados.map((d, i) => (
            <li key={d.path} role="option" aria-selected={i === sel}>
              <button
                type="button"
                onClick={() => escolher(d)}
                onMouseEnter={() => setSel(i)}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm",
                  i === sel ? "bg-primary/10 text-primary" : "hover:bg-secondary",
                )}
              >
                <span>{d.label}</span>
                <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                  {d.grupo}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
