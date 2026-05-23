import { useCallback, useState } from "react";
import {
  conciliarOfx,
  salvarHistoricoLocal,
  type Anomalia,
  type ConciliacaoResponse,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { HeroCard } from "@/components/HeroCard";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { Upload, FileText, Download } from "lucide-react";

type Modo = "simulacao" | "haiku" | "sonnet" | "opus" | "multi";

export function ConciliacaoPage() {
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [modo, setModo] = useState<Modo>("simulacao");
  const [busy, setBusy] = useState(false);
  const [resultado, setResultado] = useState<ConciliacaoResponse | null>(null);

  const onFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    setArquivos(Array.from(list));
  }, []);

  async function iniciar() {
    if (!arquivos.length) return;
    setBusy(true);
    setResultado(null);
    try {
      const data = await conciliarOfx(arquivos, {
        simular: modo === "simulacao",
        multi_modelo: modo === "multi",
        modelo: modo === "simulacao" || modo === "multi" ? undefined : modo,
      });
      setResultado(data);
      const totalTx = data.extratos.reduce((s, e) => s + e.qtd, 0);
      salvarHistoricoLocal({
        id: data.report_id,
        modo: data.modo,
        ts: new Date().toISOString(),
        total_tx: totalTx,
        total_anom: data.anomalias.length,
      });
      toast.success("Conciliação concluída");
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

      <section className="rounded-3xl border bg-card p-6 space-y-4">
        <div className="flex flex-wrap gap-2">
          {(["simulacao", "haiku", "sonnet", "opus", "multi"] as Modo[]).map((m) => (
            <Button
              key={m}
              variant={modo === m ? "default" : "outline"}
              size="sm"
              onClick={() => setModo(m)}
            >
              {m === "simulacao" ? "Simulação" : m === "multi" ? "Multi-modelo" : m}
            </Button>
          ))}
        </div>

        <label className="flex flex-col items-center justify-center border-2 border-dashed rounded-2xl p-10 cursor-pointer hover:bg-muted/30 transition-colors">
          <Upload className="h-8 w-8 text-muted-foreground mb-2" />
          <span className="text-sm text-muted-foreground">Arraste ou clique para selecionar extratos</span>
          <input
            type="file"
            multiple
            accept=".ofx,.pdf,.xml"
            className="hidden"
            onChange={(e) => onFiles(e.target.files)}
          />
        </label>

        {arquivos.length > 0 && (
          <ul className="text-sm space-y-1">
            {arquivos.map((f, i) => (
              <li key={i} className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                {f.name}
              </li>
            ))}
          </ul>
        )}

        <Button onClick={iniciar} disabled={!arquivos.length || busy}>
          {busy ? "Processando…" : "Iniciar conciliação"}
        </Button>
      </section>

      {resultado && (
        <section className="space-y-4 animate-fade-in">
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-sm font-mono text-muted-foreground">ID: {resultado.report_id}</span>
            <a href={`/export/html/${resultado.report_id}`} className="inline-flex items-center gap-1 text-sm text-primary">
              <Download className="h-4 w-4" /> HTML
            </a>
            <a href={`/export/xlsx/${resultado.report_id}`} className="inline-flex items-center gap-1 text-sm text-primary">
              <Download className="h-4 w-4" /> Excel
            </a>
            <a href={`/export/pdf/${resultado.report_id}`} className="inline-flex items-center gap-1 text-sm text-primary">
              <Download className="h-4 w-4" /> PDF
            </a>
          </div>

          <AnomaliasTable anomalias={resultado.anomalias} />

          <article className="prose prose-sm dark:prose-invert max-w-none rounded-2xl border bg-card p-6 overflow-auto max-h-[60vh]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{resultado.relatorio_md}</ReactMarkdown>
          </article>
        </section>
      )}
    </div>
  );
}

function AnomaliasTable({ anomalias }: { anomalias: Anomalia[] }) {
  if (!anomalias.length) return <p className="text-sm text-muted-foreground">Nenhuma anomalia detectada.</p>;
  return (
    <div className="overflow-auto rounded-2xl border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-2">Severidade</th>
            <th className="text-left p-2">Tipo</th>
            <th className="text-left p-2">Título</th>
            <th className="text-left p-2">Conta</th>
          </tr>
        </thead>
        <tbody>
          {anomalias.slice(0, 50).map((a, i) => (
            <tr key={i} className="border-t">
              <td className="p-2">{a.severidade}</td>
              <td className="p-2">{a.tipo}</td>
              <td className="p-2">{a.titulo}</td>
              <td className="p-2">{a.conta}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
