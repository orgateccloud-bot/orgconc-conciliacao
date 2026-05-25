import type { LucideIcon } from "lucide-react";
import { Sparkles } from "lucide-react";

interface Props {
  titulo: string;
  descricao: string;
  icone?: LucideIcon;
}

export function PlaceholderPage({ titulo, descricao, icone: Icon = Sparkles }: Props) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4 animate-fade-in">
      <div className="relative mb-6">
        <div className="h-20 w-20 rounded-2xl bg-brand-gradient flex items-center justify-center shadow-lg">
          <Icon className="h-10 w-10 text-white" />
        </div>
        <div className="absolute -right-1.5 -top-1.5 h-6 w-6 rounded-full bg-primary/20 border-2 border-background flex items-center justify-center">
          <Sparkles className="h-3 w-3 text-primary" />
        </div>
      </div>
      <h2 className="text-2xl font-semibold tracking-tight mb-2">{titulo}</h2>
      <p className="text-sm text-muted-foreground max-w-md mb-6">{descricao}</p>
      <span className="inline-flex items-center gap-1.5 rounded-full border bg-secondary px-3 py-1 text-[11px] font-mono font-semibold uppercase tracking-wider text-muted-foreground">
        Em breve
      </span>
    </div>
  );
}
