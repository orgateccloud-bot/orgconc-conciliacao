import { useCallback, useRef, useState } from "react";
import {
  conciliarOfx,
  conciliarCsv,
  salvarHistoricoLocal,
  type Anomalia,
  type ConciliacaoResponse,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { HeroCard } from "@/components/HeroCard";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { Upload, FileText, Download, X, CheckCircle2, ChevronDown, ChevronUp, Hash, AlertTriangle, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

type Modo = "simulacao" | "haiku" | "sonnet" | "opus" | "multi";
type Formato = "ofx" | "csv";

const MODO_LABELS: Record<Modo, string> = {
  simulacao: "Simulação",
  haiku: "Haiku",
  sonnet: "Sonnet",
  opus: "Opus",
  multi: "Multi-modelo",
};

const MODO_CX: Record<string, string> = {
  simulacao_local: "bg-gray-100 text-gray-700 border-gray-200",
  simulacao:       "bg-gray-100 text-gray-700 border-gray-200",
  claude_llm:      "bg-blue-100 text-blue-700 border-blue-200",
  haiku:           "bg-sky-100 text-sky-700 border-sky-200",
  sonnet:          "bg-blue-100 text-blue-700 border-blue-200",
  opus:            "bg-purple-100 text-purple-700 border-purple-200",
  multi_modelo:    "bg-purple-100 text-purple-700 border-purple-200",
  multi:           "bg-purple-100 text-purple-700 border-purple-200",
};

const MODO_LABEL_DISPLAY: Record<string, string> = {
  simulacao_local: "Simulação",
  simulacao:       "Simulação",
  claude_llm:      "Claude LLM",
  haiku:           "Haiku",
  sonnet:          "Sonnet",
  opus:            "Opus",
  multi_modelo:    "Multi-modelo",
  multi:           "Multi-modelo",
};

const SEVERIDADE_CX: Record<string, string> = {
  crítico:  "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400",
  critico:  "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400",
  alto:     "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400",
  médio:    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400",
  medio:    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400",
  baixo:    "bg-sky-100 text-sky-700 border-sky-200 dark:bg-sky-900/30 dark:text-sky-400",
  info:     "bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400",
};

const EXT_CX: Record<string, string> = {
  ofx: "bg-blue-100 text-blue-700",
  pdf: "bg-red-100 text-red-700",
  xml: "bg-orange-100 text-orange-700",
  csv: "bg-green-100 text-green-700",
};

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

export function ConciliacaoPage() {
  const [formato, setFormato] = useState<Formato>("ofx");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [modo, setModo] = useState<Modo>("simulacao");
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resultado, setResultado] = useState<ConciliacaoResponse | null>(null);
  // MELHORIA 3: toggle para expandir/recolher relatório
  const [expandido, setExpandido] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = formato === "csv" ? ".csv" : ".ofx,.pdf,.xml";

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    const news = Array.from(list);
    setArquivos((prev) => {
      const combined = [...prev, ...news];
      return formato === "csv" ? combined.slice(-2) : combined.slice(0, 50);
    });
  }, [formato]);

  function removeFile(i: number) {
    setArquivos((prev) => prev.filter((_, idx) => idx !== i));
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  }

  async function iniciar() {
    if (!arquivos.length) return;
    setBusy(true);
    setResultado(null);
    setExpandido(false);
    try {
      const opts = {
        simular: modo === "simulacao",
        multi_modelo: modo === "multi",
        modelo: modo === "simulacao" || modo === "multi" ? undefined : modo,
      };
      const data = formato === "csv"
        ? await conciliarCsv(arquivos, opts)
        : await conciliarOfx(arquivos, opts);
      setResultado(data);
      const totalTx = data.extratos.reduce((s, e) => s + e.qtd, 0);
      salvarHistoricoLocal({
        id: data.report_id,
        modo: data.modo,
        ts: new Date().toISOString(),
        total_tx: totalTx,
        total_anom: data.anomalias.length,
      });
      toast.success(`Conciliação concluída — ${data.anomalias.length} anomalia(s) detectada(s)`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro na conciliação");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="01 · CONCILIAÇÃO"
        title="Nova carta de"
        titleAccent="conciliação."
        subtitle="Carregue OFX, PDF ou XML. Modo simulação é gratuito; modelos Claude exigem API key no servidor."
      />

      <section className="rounded-3xl border glass p-6 space-y-5">
        {/* Formato tabs */}
        <div className="flex gap-1 p-1 rounded-xl bg-muted w-fit">
          {(["ofx", "csv"] as Formato[]).map((f) => (
            <button
              key={f}
              onClick={() => { setFormato(f); setArquivos([]); }}
              className={cn(
                "px-4 py-1.5 text-sm rounded-lg font-medium transition-colors",
                formato === f
                  ? "bg-card shadow text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {f === "ofx" ? "OFX · PDF · XML" : "CSV (extrato + razão)"}
            </button>
          ))}
        </div>

        {/* Mode selector */}
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {(["simulacao", "haiku", "sonnet", "opus", "multi"] as Modo[]).map((m) => (
              <Button
                key={m}
                variant={modo === m ? "default" : "outline"}
                size="sm"
                onClick={() => setModo(m)}
              >
                {MODO_LABELS[m]}
              </Button>
            ))}
          </div>
          {/* MELHORIA 6: aviso de custo quando Opus selecionado */}
          {modo === "opus" && (
            <p className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
              <span>⚠️</span>
              <span>Opus consome ~10× mais créditos que Sonnet</span>
            </p>
          )}
        </div>

        {/* Drop zone */}
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className={cn(
            "flex flex-col items-center justify-center border-2 border-dashed rounded-2xl p-10 cursor-pointer transition-all select-none",
            dragOver
              ? "border-primary bg-primary/5 scale-[1.01]"
              : "hover:bg-muted/30 hover:border-primary/50"
          )}
        >
          <Upload className={cn("h-8 w-8 mb-2 transition-colors", dragOver ? "text-primary" : "text-muted-foreground")} />
          <span className="text-sm text-muted-foreground text-center">
            {formato === "csv"
              ? "Arraste ou clique — até 2 arquivos CSV (extrato e razão contábil)"
              : "Arraste ou clique — OFX, PDF ou XML (até 50 arquivos)"}
          </span>
          <input
            ref={inputRef}
            type="file"
            multiple={formato !== "csv"}
            accept={accept}
            className="hidden"
            onChange={(e) => addFiles(e.target.files)}
          />
        </div>

        {/* File list */}
        {arquivos.length > 0 && (
          <ul className="space-y-2">
            {arquivos.map((f, i) => {
              const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
              return (
                <li key={i} className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1 truncate font-mono text-xs">{f.name}</span>
                  <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-bold uppercase font-mono", EXT_CX[ext] ?? "bg-gray-100 text-gray-600")}>
                    {ext}
                  </span>
                  <span className="text-xs text-muted-foreground shrink-0">{formatBytes(f.size)}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                    className="rounded p-0.5 hover:bg-secondary text-muted-foreground"
                    aria-label="Remover arquivo"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <Button onClick={iniciar} disabled={!arquivos.length || busy} className="gap-2">
          {busy ? (
            <>
              <span className="h-4 w-4 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin" />
              Processando…
            </>
          ) : "Iniciar conciliação"}
        </Button>
      </section>

      {resultado && (
        <section className="space-y-4 animate-fade-in">
          <div className="flex flex-wrap gap-3 items-center rounded-2xl border glass p-4">
            <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
            <span className="text-sm font-mono text-muted-foreground flex-1 truncate">
              ID: {resultado.report_id}
            </span>
            <div className="flex gap-2 flex-wrap">
              {[
                { label: "HTML", path: `/export/html/${resultado.report_id}` },
                { label: "Excel", path: `/export/xlsx/${resultado.report_id}` },
                { label: "PDF", path: `/export/pdf/${resultado.report_id}` },
              ].map(({ label, path }) => (
                <a
                  key={label}
                  href={path}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/5 transition-colors"
                >
                  <Download className="h-3.5 w-3.5" />
                  {label}
                </a>
              ))}
            </div>
          </div>

          {/* MELHORIA 2: KPI cards pós-conciliação */}
          <KpiCards resultado={resultado} modoLabel={MODO_LABEL_DISPLAY} modoCx={MODO_CX} />

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
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{resultado.relatorio_md}</ReactMarkdown>
              </article>
              {/* gradiente de fade quando recolhido */}
              {!expandido && (
                <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-card to-transparent" />
              )}
            </div>
          </div>
        </section>
      )}
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
