import { useState } from "react";
import { Activity, AlertTriangle, CheckCircle2, Lock, Info } from "lucide-react";
import type { AuditEventSummary, AuditTimelineResponse } from "@/lib/api";
import { AuditEventModal } from "./AuditEventModal";
import { cn } from "@/lib/utils";

interface Props {
  data: AuditTimelineResponse | null;
}

const ACTION_ICONE: Record<string, { Icon: typeof Activity; cor: string }> = {
  "login.success":      { Icon: Lock,         cor: "text-blue-500" },
  "conciliacao.criar":  { Icon: CheckCircle2, cor: "text-green-500" },
  "cliente.criar":      { Icon: Info,         cor: "text-primary" },
  "cliente.atualizar":  { Icon: Info,         cor: "text-primary" },
  "anomalia.detectada": { Icon: AlertTriangle, cor: "text-orange-500" },
};

export function AuditTimeline({ data }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (data === null) {
    return (
      <div className="flex items-center justify-center h-24 text-sm text-muted-foreground">
        Auditoria indisponível
      </div>
    );
  }

  return (
    <>
      <div className="rounded-3xl border glass p-6">
        <Header total={data.total} integra={data.cadeia_integra} motivo={data.cadeia_motivo} />
        {data.eventos.length === 0 ? (
          <p className="text-xs text-muted-foreground py-6 text-center">
            Nenhum evento registrado ainda. Eventos aparecem após login, conciliação ou alteração de clientes.
          </p>
        ) : (
          <ol className="mt-4 space-y-2">
            {data.eventos.map((ev) => (
              <EventRow key={ev.id} evento={ev} onOpen={() => setSelectedId(ev.id)} />
            ))}
          </ol>
        )}
      </div>

      {selectedId && (
        <AuditEventModal evento_id={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </>
  );
}

function Header({
  total,
  integra,
  motivo,
}: {
  total: number;
  integra: boolean;
  motivo?: string | null;
}) {
  return (
    <div className="flex items-center gap-2">
      <Activity className="h-4 w-4 text-muted-foreground" />
      <h3 className="text-sm font-semibold">Trilha de auditoria</h3>
      <span className="ml-auto inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-semibold"
        title={integra ? "Hash chain íntegra" : (motivo ?? "Cadeia comprometida")}
        style={{
          background: integra ? "rgba(22,163,74,0.12)" : "rgba(220,38,38,0.12)",
          color: integra ? "#16a34a" : "#dc2626",
        }}
      >
        <Lock className="h-2.5 w-2.5" />
        {integra ? "Íntegra" : "Comprometida"}
      </span>
      <span className="text-[10px] font-mono text-muted-foreground">{total} eventos</span>
    </div>
  );
}

function EventRow({
  evento,
  onOpen,
}: {
  evento: AuditEventSummary;
  onOpen: () => void;
}) {
  const meta = ACTION_ICONE[evento.action] ?? { Icon: Activity, cor: "text-muted-foreground" };
  const Icon = meta.Icon;

  return (
    <li>
      <button
        onClick={onOpen}
        className="w-full flex items-start gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-muted/30 transition-colors group"
      >
        <div className={cn("rounded-md bg-muted/30 p-1.5 shrink-0 mt-0.5", meta.cor)}>
          <Icon className="h-3.5 w-3.5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium truncate">{descrever(evento.action)}</span>
            {evento.resource_id && (
              <span className="font-mono text-[11px] text-muted-foreground truncate">
                · {evento.resource_id.slice(0, 14)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5 text-[11px] text-muted-foreground">
            <span>{evento.actor_email ?? evento.actor_sub ?? "sistema"}</span>
            <span>·</span>
            <span>{evento.ts ? new Date(evento.ts).toLocaleString("pt-BR") : "—"}</span>
          </div>
        </div>
        <span
          className="font-mono text-[10px] text-muted-foreground bg-muted/40 px-1.5 py-0.5 rounded shrink-0 group-hover:bg-muted"
          title={`Hash completo: ${evento.payload_hash}`}
        >
          {evento.payload_hash_short ?? "—"}
        </span>
      </button>
    </li>
  );
}

function descrever(action: string): string {
  const map: Record<string, string> = {
    "login.success": "Login bem-sucedido",
    "conciliacao.criar": "Conciliação criada",
    "cliente.criar": "Cliente cadastrado",
    "cliente.atualizar": "Cliente atualizado",
  };
  return map[action] ?? action;
}
