import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  baixarExport,
  type Anomalia,
  type ConciliacaoResponse,
} from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { HeroCard } from "@/components/HeroCard";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { Download, CheckCircle2, ChevronDown, ChevronUp, Hash, AlertTriangle, Activity, Upload as UploadIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { MODO_CX, MODO_LABEL } from "@/lib/constants";

const SEVERIDADE_CX: Record<string, string> = {
  crítico:  "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400",
  critico:  "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400",
  alto:     "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400",
  médio:    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400",
  medio:    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400",
  baixo:    "bg-sky-100 text-sky-700 border-sky-200 dark:bg-sky-900/30 dark:text-sky-400",
  info:     "bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400",
};

export function ConciliacaoPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [expandido, setExpandido] = useState(false);

  // Recebe o resultado vindo do UploadPage via router state, com fallback para sessionStorage
  const resultadoInicial = (location.state as { resultado?: ConciliacaoResponse })?.resultado ?? (() => {
    try { const s = sessionStorage.getItem('orgconc.last_resultado'); return s ? JSON.parse(s) : null }
    catch { return null }
  })()
  const resultado: ConciliacaoResponse | null = resultadoInicial;

  if (!resultado) {
    return (
      <div className="space-y-8">
        <HeroCard
          eyebrow="01 · ANÁLISES"
          title="Resultado da"
          titleAccent="conciliação."
          subtitle="Faça o upload dos extratos para iniciar uma nova análise."
        />
        <div className="rounded-3xl border glass p-12 flex flex-col items-center gap-4 text-center">
          <UploadIcon className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-muted-foreground text-sm">
            Nenhuma análise ativa. Envie seus extratos para ver os resultados aqui.
          </p>
          <Button onClick={() => navigate("/upload")} className="gap-2">
            <UploadIcon className="h-4 w-4" />
            Ir para Upload
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="01 · ANÁLISES"
        title="Resultado da"
        titleAccent="conciliação."
        subtitle="Confira as anomalias detectadas e baixe o relatório completo."
      />

      <section className="space-y-4 animate-fade-in">
          <div className="flex flex-wrap gap-3 items-center rounded-2xl border glass p-4">
            <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
            <span className="text-sm font-mono text-muted-foreground flex-1 truncate">
              ID: {resultado.report_id}
            </span>
            <div className="flex gap-2 flex-wrap">
              {/* Download autenticado (Bearer via apiFetchBlob) — link direto dava 401 */}
              {[
                { label: "HTML", ext: "html" },
                { label: "Excel", ext: "xlsx" },
                { label: "PDF", ext: "pdf" },
              ].map(({ label, ext }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() =>
                    baixarExport(
                      `/export/${ext}/${resultado.report_id}`,
                      `conciliacao_${resultado.report_id}.${ext}`,
                    ).catch(() => toast.error(`Falha ao baixar ${label}`))
                  }
                  className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/5 transition-colors"
                >
                  <Download className="h-3.5 w-3.5" />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* MELHORIA 2: KPI cards pós-conciliação */}
          <KpiCards resultado={resultado} modoLabel={MODO_LABEL} modoCx={MODO_CX} />

          <AnomaliasTable anomalias={resultado.anomalias} />

          {/* MELHORIA 3: relatório Markdown com toggle expandir/recolher */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-mono uppercase tracking-wide">Relatório</span>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 h-7 text-xs"
                onClick={() => setExpandido((v) => !v)}
              >
                {expandido ? (
                  <>
                    <ChevronUp className="h-3.5 w-3.5" />
                    Recolher
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3.5 w-3.5" />
                    Expandir relatório
                  </>
                )}
              </Button>
            </div>
            <div className="relative rounded-2xl border glass overflow-hidden">
              <article
                className={cn(
                  "prose prose-sm dark:prose-invert max-w-none p-6",
                  expandido ? "" : "max-h-[40vh] overflow-y-auto"
                )}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{resultado.relatorio_md}</ReactMarkdown>
              </article>
              {/* gradiente de fade quando recolhido */}
              {!expandido && (
                <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-16 bg-linear-to-t from-card to-transparent" />
              )}
            </div>
          </div>
      </section>
    </div>
  );
}

// MELHORIA 2: componente de KPI cards
function KpiCards({
  resultado,
  modoLabel,
  modoCx,
}: {
  resultado: ConciliacaoResponse;
  modoLabel: Record<string, string>;
  modoCx: Record<string, string>;
}) {
  const totalTx = resultado.extratos.reduce((s, e) => s + e.qtd, 0);
  const totalAnom = resultado.anomalias.length;
  const modoBadgeCx = modoCx[resultado.modo] ?? "bg-gray-100 text-gray-700 border-gray-200";
  const modoDisplay = modoLabel[resultado.modo] ?? resultado.modo;

  return (
    <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
      {/* Total Transações */}
      <div className="rounded-xl border glass p-4 flex items-start gap-3">
        <div className="rounded-lg p-2 text-primary bg-primary/10 shrink-0">
          <Hash className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">Total Transações</p>
          <p className="text-xl font-bold mt-0.5">{totalTx.toLocaleString("pt-BR")}</p>
        </div>
      </div>

      {/* Total Créditos — sem dados diretos no response */}
      <div className="rounded-xl border glass p-4 flex items-start gap-3">
        <div className="rounded-lg p-2 text-blue-500 bg-blue-50 dark:bg-blue-950/30 shrink-0">
          <Activity className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">Total Créditos</p>
          <p className="text-sm font-medium mt-1 text-muted-foreground">Ver relatório</p>
        </div>
      </div>

      {/* Total Anomalias */}
      <div className="rounded-xl border glass p-4 flex items-start gap-3">
        <div className="rounded-lg p-2 text-orange-500 bg-orange-50 dark:bg-orange-950/30 shrink-0">
          <AlertTriangle className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">Total Anomalias</p>
          <p className={cn("text-xl font-bold mt-0.5", totalAnom > 0 ? "text-orange-500" : "")}>
            {totalAnom}
          </p>
        </div>
      </div>

      {/* Modo */}
      <div className="rounded-xl border glass p-4 flex items-start gap-3">
        <div className="rounded-lg p-2 text-purple-500 bg-purple-50 dark:bg-purple-950/30 shrink-0">
          <Activity className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">Modo</p>
          <div className="mt-1.5">
            <span
              className={cn(
                "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold",
                modoBadgeCx
              )}
            >
              {modoDisplay}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function AnomaliasTable({ anomalias }: { anomalias: Anomalia[] }) {
  if (!anomalias.length) {
    return (
      <div className="rounded-2xl border glass p-6 flex items-center gap-3 text-sm text-muted-foreground">
        <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
        Nenhuma anomalia detectada.
      </div>
    );
  }

  return (
    <div className="overflow-auto rounded-2xl border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-2 font-semibold">Severidade</th>
            <th className="text-left p-2 font-semibold">Tipo</th>
            <th className="text-left p-2 font-semibold">Título</th>
            <th className="text-left p-2 font-semibold">Conta</th>
            <th className="text-right p-2 font-semibold">Valor (R$)</th>
            {/* MELHORIA 1: coluna Detalhe */}
            <th className="text-left p-2 font-semibold">Detalhe</th>
          </tr>
        </thead>
        <tbody>
          {anomalias.slice(0, 50).map((a, i) => {
            const sevLower = a.severidade?.toLowerCase() ?? "info";
            const cx = SEVERIDADE_CX[sevLower] ?? SEVERIDADE_CX.info;
            // truncar detalhe a 80 chars para exibição
            const detalheDisplay = a.detalhe
              ? a.detalhe.length > 80
                ? a.detalhe.slice(0, 80) + "…"
                : a.detalhe
              : "—";
            return (
              <tr key={i} className="border-t hover:bg-muted/30">
                <td className="p-2">
                  <span className={cn("inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold", cx)}>
                    {a.severidade}
                  </span>
                </td>
                <td className="p-2 text-muted-foreground">{a.tipo}</td>
                <td className="p-2 font-medium">{a.titulo}</td>
                <td className="p-2 font-mono text-xs">{a.conta}</td>
                <td className="p-2 text-right font-mono">
                  {a.valor != null
                    ? a.valor.toLocaleString("pt-BR", { minimumFractionDigits: 2 })
                    : "—"}
                </td>
                {/* MELHORIA 1: célula Detalhe com tooltip no title */}
                <td
                  className="p-2 text-xs text-muted-foreground max-w-[200px] truncate"
                  title={a.detalhe ?? undefined}
                >
                  {detalheDisplay}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {anomalias.length > 50 && (
        <p className="p-3 text-center text-xs text-muted-foreground border-t">
          Exibindo 50 de {anomalias.length} anomalias. Baixe o relatório completo para ver todas.
        </p>
      )}
    </div>
  );
}
