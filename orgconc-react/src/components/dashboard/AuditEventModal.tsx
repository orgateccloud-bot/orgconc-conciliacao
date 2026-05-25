import { useEffect, useState } from "react";
import { ApiError, fetchAuditEvento, type AuditEventDetalhe } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { CheckCircle2, XCircle, Lock } from "lucide-react";

interface Props {
  evento_id: string;
  onClose: () => void;
}

export function AuditEventModal({ evento_id, onClose }: Props) {
  const [data, setData] = useState<AuditEventDetalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setErro(null);
    setData(null);
    fetchAuditEvento(evento_id)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (cancelled) return;
        setErro(e instanceof ApiError ? e.message : "Falha ao carregar evento");
      });
    return () => {
      cancelled = true;
    };
  }, [evento_id]);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Lock className="h-4 w-4" />
            Evento de auditoria
          </DialogTitle>
        </DialogHeader>

        {erro && (
          <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">{erro}</div>
        )}

        {!data && !erro && (
          <div className="text-sm text-muted-foreground py-6 text-center">Carregando…</div>
        )}

        {data && (
          <div className="space-y-4 text-sm">
            <Linha label="Ação" value={data.action} mono />
            <Linha label="Quando" value={data.ts ? new Date(data.ts).toLocaleString("pt-BR") : "—"} />
            <Linha label="Ator" value={data.actor_email ?? data.actor_sub ?? "sistema"} />
            {data.resource_type && <Linha label="Recurso" value={`${data.resource_type} · ${data.resource_id ?? "—"}`} mono />}
            <Linha label="Request ID" value={data.request_id ?? "—"} mono />

            <div className="border-t pt-3">
              <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-muted-foreground mb-2">
                Hash chain
                {data.payload_hash_valid ? (
                  <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400">
                    <CheckCircle2 className="h-3 w-3" /> íntegro
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-red-600 dark:text-red-400">
                    <XCircle className="h-3 w-3" /> comprometido
                  </span>
                )}
              </div>
              <Linha label="payload_hash" value={data.payload_hash} mono />
              <Linha label="prev_hash" value={data.prev_hash} mono />
            </div>

            <div className="border-t pt-3">
              <div className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground mb-2">
                Payload (PII mascarada)
              </div>
              <pre className="text-xs bg-muted/40 rounded-md p-3 overflow-auto max-h-64 font-mono leading-relaxed">
                {JSON.stringify(data.payload, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Linha({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 items-baseline">
      <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className={mono ? "font-mono text-xs break-all" : "text-sm"}>{value}</span>
    </div>
  );
}
