import { Activity, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import type { ActivityFeedItem } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  data: ActivityFeedItem[];
}

const ICONE_POR_SEV: Record<string, { Icon: typeof Info; cor: string }> = {
  success: { Icon: CheckCircle2,  cor: "text-green-500" },
  warn:    { Icon: AlertTriangle, cor: "text-orange-500" },
  info:    { Icon: Info,          cor: "text-primary" },
};

export function ActivityFeed({ data }: Props) {
  const items = data ?? [];
  return (
    <div className="rounded-2xl border glass p-5">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
          Atividade Auditada
        </span>
      </div>

      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground leading-relaxed">
          Nenhum evento ainda. Eventos aparecem após login, conciliação ou alteração de clientes.
        </p>
      ) : (
        <ol className="space-y-2.5">
          {items.map((item) => (
            <FeedItem key={item.id} item={item} />
          ))}
        </ol>
      )}
    </div>
  );
}

function FeedItem({ item }: { item: ActivityFeedItem }) {
  const meta = ICONE_POR_SEV[item.severidade] ?? ICONE_POR_SEV.info;
  const Icon = meta.Icon;
  const quando = item.ts ? formatarRelativo(item.ts) : "—";

  return (
    <li className="flex items-start gap-2.5">
      <div className={cn("rounded-md bg-muted/30 p-1 shrink-0 mt-0.5", meta.cor)}>
        <Icon className="h-3 w-3" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium leading-tight truncate">{item.titulo}</p>
        <p className="text-[10px] text-muted-foreground mt-0.5 truncate">
          {item.ator} · {quando}
        </p>
      </div>
    </li>
  );
}

function formatarRelativo(iso: string): string {
  const agora = Date.now();
  const t = new Date(iso).getTime();
  const dm = Math.max(0, Math.round((agora - t) / 60000));
  if (dm < 1) return "agora";
  if (dm < 60) return `${dm} min`;
  const dh = Math.round(dm / 60);
  if (dh < 24) return `${dh}h`;
  const dd = Math.round(dh / 24);
  return `${dd}d`;
}
