import type { TransacaoRecente } from "@/lib/api";
import { Receipt } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  data: TransacaoRecente[];
}

const FORMATADOR_BRL = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 2,
});

export function TransacoesRecentes({ data }: Props) {
  return (
    <div className="rounded-3xl border glass p-6">
      <div className="flex items-center gap-2 mb-5">
        <Receipt className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Transações recentes</h3>
        <span className="ml-auto text-[11px] font-mono text-muted-foreground">
          {data.length > 0 ? `últimas ${data.length}` : "sem dados"}
        </span>
      </div>

      {data.length === 0 ? (
        <div className="py-10 text-center text-xs text-muted-foreground">
          Nenhuma transação persistida ainda. Faça uma conciliação para popular.
        </div>
      ) : (
        <div className="table-responsive">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                <th className="py-2 text-left font-semibold">Data</th>
                <th className="py-2 text-left font-semibold hidden sm:table-cell">Memo</th>
                <th className="py-2 text-left font-semibold hidden md:table-cell">Categoria</th>
                <th className="py-2 text-center font-semibold">Status</th>
                <th className="py-2 text-right font-semibold">Valor</th>
              </tr>
            </thead>
            <tbody>
              {data.map((t) => (
                <tr key={t.id} className="border-b last:border-0 hover:bg-muted/20 transition-colors">
                  <td className="py-2 pr-2 font-mono text-xs text-muted-foreground whitespace-nowrap">
                    {t.data_lancamento
                      ? new Date(t.data_lancamento).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })
                      : "—"}
                  </td>
                  <td className="py-2 pr-2 hidden sm:table-cell truncate max-w-[260px]">
                    {t.memo ?? "—"}
                  </td>
                  <td className="py-2 pr-2 hidden md:table-cell">
                    <CategoriaPill categoria={t.categoria} />
                  </td>
                  <td className="py-2 text-center">
                    <StatusPill anomalia={t.eh_anomalia} />
                  </td>
                  <td
                    className={cn(
                      "py-2 pl-2 text-right font-mono tabular text-xs whitespace-nowrap",
                      (t.valor ?? 0) < 0
                        ? "text-orange-600 dark:text-orange-400"
                        : "text-green-600 dark:text-green-400"
                    )}
                  >
                    {t.valor !== null ? FORMATADOR_BRL.format(t.valor) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusPill({ anomalia }: { anomalia: boolean }) {
  if (anomalia) {
    return (
      <span className="inline-flex items-center rounded-full bg-orange-100 dark:bg-orange-950/50 px-2 py-0.5 text-[10px] font-semibold text-orange-700 dark:text-orange-400">
        Anomalia
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-green-100 dark:bg-green-950/50 px-2 py-0.5 text-[10px] font-semibold text-green-700 dark:text-green-400">
      OK
    </span>
  );
}

function CategoriaPill({ categoria }: { categoria: string | null }) {
  if (!categoria) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <span className="inline-flex items-center rounded-md bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
      {categoria}
    </span>
  );
}
