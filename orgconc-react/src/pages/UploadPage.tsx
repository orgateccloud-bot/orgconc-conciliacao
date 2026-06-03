import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  conciliarOfx,
  conciliarCsv,
  salvarHistoricoLocal,
  type ConciliacaoResponse,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { HeroCard } from "@/components/HeroCard";
import { toast } from "sonner";
import { Upload, FileText, X } from "lucide-react";
import { cn, formatBytes } from "@/lib/utils";

type Modo = "simulacao" | "haiku" | "sonnet" | "opus" | "multi";
type Formato = "ofx" | "csv";

const MODO_LABELS: Record<Modo, string> = {
  simulacao: "Simulação",
  haiku: "Haiku",
  sonnet: "Sonnet",
  opus: "Opus",
  multi: "Multi-modelo",
};

const EXT_CX: Record<string, string> = {
  ofx: "bg-blue-100 text-blue-700",
  pdf: "bg-red-100 text-red-700",
  xml: "bg-orange-100 text-orange-700",
  csv: "bg-green-100 text-green-700",
};

export function UploadPage() {
  const navigate = useNavigate();
  const [formato, setFormato] = useState<Formato>("ofx");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [modo, setModo] = useState<Modo>("simulacao");
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = formato === "csv" ? ".csv" : ".ofx,.pdf,.xml";

  const addFiles = useCallback(
    (list: FileList | null) => {
      if (!list) return;
      const news = Array.from(list);
      setArquivos((prev) => {
        const combined = [...prev, ...news];
        return formato === "csv" ? combined.slice(-2) : combined.slice(0, 50);
      });
    },
    [formato]
  );

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
    try {
      const opts = {
        simular: modo === "simulacao",
        multi_modelo: modo === "multi",
        modelo: modo === "simulacao" || modo === "multi" ? undefined : modo,
      };
      const data: ConciliacaoResponse =
        formato === "csv"
          ? await conciliarCsv(arquivos, opts)
          : await conciliarOfx(arquivos, opts);

      const totalTx = data.extratos.reduce((s, e) => s + e.qtd, 0);
      salvarHistoricoLocal({
        id: data.report_id,
        modo: data.modo,
        ts: new Date().toISOString(),
        total_tx: totalTx,
        total_anom: data.anomalias.length,
      });

      toast.success(
        `Conciliação concluída — ${data.anomalias.length} anomalia(s)`
      );
      try { sessionStorage.setItem('orgconc.last_resultado', JSON.stringify(data)) } catch { /* quota */ }
      navigate("/conciliacao", { state: { resultado: data } });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro na conciliação");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="02 · UPLOAD"
        title="Enviar extratos para"
        titleAccent="conciliação."
        subtitle="Carregue OFX, PDF ou XML. Modo simulação é gratuito; modelos Claude exigem API key no servidor."
      />

      <section className="rounded-3xl border glass p-6 space-y-5">
        {/* Formato tabs */}
        <div className="flex gap-1 p-1 rounded-xl bg-muted w-fit">
          {(["ofx", "csv"] as Formato[]).map((f) => (
            <button
              key={f}
              onClick={() => {
                setFormato(f);
                setArquivos([]);
              }}
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
            {(["simulacao", "haiku", "sonnet", "opus", "multi"] as Modo[]).map(
              (m) => (
                <Button
                  key={m}
                  variant={modo === m ? "default" : "outline"}
                  size="sm"
                  onClick={() => setModo(m)}
                >
                  {MODO_LABELS[m]}
                </Button>
              )
            )}
          </div>
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
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className={cn(
            "flex flex-col items-center justify-center border-2 border-dashed rounded-2xl p-10 cursor-pointer transition-all select-none",
            dragOver
              ? "border-primary bg-primary/5 scale-[1.01]"
              : "hover:bg-muted/30 hover:border-primary/50"
          )}
        >
          <Upload
            className={cn(
              "h-8 w-8 mb-2 transition-colors",
              dragOver ? "text-primary" : "text-muted-foreground"
            )}
          />
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
                <li
                  key={i}
                  className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm"
                >
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1 truncate font-mono text-xs">
                    {f.name}
                  </span>
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-bold uppercase font-mono",
                      EXT_CX[ext] ?? "bg-gray-100 text-gray-600"
                    )}
                  >
                    {ext}
                  </span>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {formatBytes(f.size)}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(i);
                    }}
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

        <Button
          onClick={iniciar}
          disabled={!arquivos.length || busy}
          className="gap-2"
        >
          {busy ? (
            <>
              <span className="h-4 w-4 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin" />
              Processando…
            </>
          ) : (
            "Iniciar conciliação"
          )}
        </Button>
      </section>
    </div>
  );
}
