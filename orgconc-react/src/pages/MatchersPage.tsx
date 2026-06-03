import { useCallback, useEffect, useRef, useState } from "react";
import {
  conciliarMatchers,
  listarClientes,
  type Cliente,
  type DisposicaoItem,
  type MatchersResponse,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { HeroCard } from "@/components/HeroCard";
import { toast } from "sonner";
import { FileText, X, Network, CheckCircle2, AlertTriangle, Hash } from "lucide-react";
import { cn, formatBytes } from "@/lib/utils";

const DISP_COLOR: Record<string, string> = {
  RESOLVIDO_CADASTRO:    "bg-blue-100 text-blue-700 border-blue-200",
  RESOLVIDO_BASE:        "bg-blue-100 text-blue-700 border-blue-200",
  RESOLVIDO_NFE:         "bg-green-100 text-green-700 border-green-200",
  RESOLVIDO_GUIA:        "bg-green-100 text-green-700 border-green-200",
  RESOLVIDO_CONTRATO:    "bg-green-100 text-green-700 border-green-200",
  TARIFA_BANCARIA:       "bg-gray-100 text-gray-700 border-gray-200",
  TRANSFERENCIA_INTERNA: "bg-gray-100 text-gray-700 border-gray-200",
  PENDENTE_REVISAO:      "bg-orange-100 text-orange-700 border-orange-200",
  PENDENTE_MATCHER:      "bg-orange-100 text-orange-700 border-orange-200",
  PENDENTE_FUZZY:        "bg-yellow-100 text-yellow-700 border-yellow-200",
  NAO_ENCONTRADO:        "bg-red-100 text-red-700 border-red-200",
  DOC_INVALIDO:          "bg-red-100 text-red-700 border-red-200",
};

const EXT_CX: Record<string, string> = {
  ofx: "bg-blue-100 text-blue-700",
  xml: "bg-orange-100 text-orange-700",
  zip: "bg-purple-100 text-purple-700",
};

function formatBRL(v: number): string {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function MatchersPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clienteId, setClienteId] = useState<string>("");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resultado, setResultado] = useState<MatchersResponse | null>(null);
  const [filtroPendentes, setFiltroPendentes] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => toast.error("Falha ao carregar clientes"));
  }, []);

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    const news = Array.from(list).slice(0, 50);
    setArquivos((prev) => [...prev, ...news].slice(0, 100));
  }, []);

  function removeFile(i: number) {
    setArquivos((prev) => prev.filter((_, idx) => idx !== i));
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  }

  async function executar() {
    if (!clienteId) {
      toast.error("Selecione um cliente");
      return;
    }
    if (!arquivos.length) {
      toast.error("Envie ao menos 1 arquivo OFX");
      return;
    }
    setBusy(true);
    setResultado(null);
    try {
      const r = await conciliarMatchers(clienteId, arquivos);
      setResultado(r);
      toast.success(
        `${r.automatizadas}/${r.total_transacoes} automatizadas (${r.taxa_automatizacao_pct}%)`
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro na conciliação");
    } finally {
      setBusy(false);
    }
  }

  const disposicoesFiltradas = (resultado?.disposicoes ?? []).filter((d) =>
    filtroPendentes ? d.disposicao.startsWith("PENDENTE_") || d.disposicao === "NAO_ENCONTRADO" : true
  );

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="MATCHERS · 6 ESTÁGIOS"
        title="Conciliação contábil"
        titleAccent="automática."
        subtitle="Cascata de 6 estágios: transferência interna → CNPJ → NF-e → tarifa → tributo → contrato → alias. Cada transação recebe disposição contábil pronta para validação."
      />

      <section className="rounded-3xl border glass p-6 space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Cliente</Label>
            <Select value={clienteId} onValueChange={setClienteId}>
              <SelectTrigger>
                <SelectValue placeholder="Selecione um cliente cadastrado" />
              </SelectTrigger>
              <SelectContent>
                {clientes.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.nome} {c.cnpj && `(${c.cnpj})`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

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
          <Network className={cn("h-8 w-8 mb-2 transition-colors", dragOver ? "text-primary" : "text-muted-foreground")} />
          <span className="text-sm text-muted-foreground text-center">
            Arraste OFX + XMLs de NF-e (ou ZIP com tudo)
          </span>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".ofx,.xml,.zip"
            className="hidden"
            onChange={(e) => addFiles(e.target.files)}
          />
        </div>

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

        <Button onClick={executar} disabled={!arquivos.length || !clienteId || busy} className="gap-2">
          {busy ? (
            <>
              <span className="h-4 w-4 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin" />
              Processando cascata…
            </>
          ) : (
            <>
              <Network className="h-4 w-4" />
              Executar conciliação
            </>
          )}
        </Button>
      </section>

      {resultado && (
        <section className="space-y-4 animate-fade-in">
          {/* KPIs */}
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border glass p-4 flex items-start gap-3">
              <div className="rounded-lg p-2 text-primary bg-primary/10 shrink-0">
                <Hash className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">Total</p>
                <p className="text-xl font-bold mt-0.5">{resultado.total_transacoes}</p>
              </div>
            </div>
            <div className="rounded-xl border glass p-4 flex items-start gap-3">
              <div className="rounded-lg p-2 text-green-500 bg-green-50 dark:bg-green-950/30 shrink-0">
                <CheckCircle2 className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">Automatizadas</p>
                <p className="text-xl font-bold mt-0.5 text-green-600">{resultado.automatizadas}</p>
              </div>
            </div>
            <div className="rounded-xl border glass p-4 flex items-start gap-3">
              <div className="rounded-lg p-2 text-orange-500 bg-orange-50 dark:bg-orange-950/30 shrink-0">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">Pendentes</p>
                <p className="text-xl font-bold mt-0.5 text-orange-600">
                  {resultado.total_transacoes - resultado.automatizadas}
                </p>
              </div>
            </div>
            <div className="rounded-xl border glass p-4 flex items-start gap-3">
              <div className="rounded-lg p-2 text-purple-500 bg-purple-50 dark:bg-purple-950/30 shrink-0">
                <Network className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">Taxa</p>
                <p className="text-xl font-bold mt-0.5 text-purple-600">{resultado.taxa_automatizacao_pct}%</p>
              </div>
            </div>
          </div>

          {/* Filtro */}
          <div className="flex items-center gap-3">
            <Button
              variant={filtroPendentes ? "default" : "outline"}
              size="sm"
              onClick={() => setFiltroPendentes((v) => !v)}
            >
              {filtroPendentes ? "Mostrar todas" : "Apenas pendentes"}
            </Button>
            <span className="text-xs text-muted-foreground">
              {disposicoesFiltradas.length} de {resultado.disposicoes.length}
            </span>
          </div>

          {/* Tabela de disposições */}
          <DisposicoesTable disposicoes={disposicoesFiltradas} />
        </section>
      )}
    </div>
  );
}

function DisposicoesTable({ disposicoes }: { disposicoes: DisposicaoItem[] }) {
  if (!disposicoes.length) {
    return (
      <div className="rounded-2xl border glass p-6 text-center text-sm text-muted-foreground">
        Nenhuma transação para exibir.
      </div>
    );
  }
  return (
    <div className="overflow-auto rounded-2xl border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-2 font-semibold">Data</th>
            <th className="text-right p-2 font-semibold">Valor (R$)</th>
            <th className="text-left p-2 font-semibold">Memo / Nome</th>
            <th className="text-left p-2 font-semibold">Disposição</th>
            <th className="text-left p-2 font-semibold">Contraparte</th>
            <th className="text-left p-2 font-semibold">Origem</th>
            <th className="text-left p-2 font-semibold">Flag</th>
          </tr>
        </thead>
        <tbody>
          {disposicoes.slice(0, 200).map((d, i) => {
            const cx = DISP_COLOR[d.disposicao] ?? "bg-gray-100 text-gray-700 border-gray-200";
            return (
              <tr key={i} className="border-t hover:bg-muted/30">
                <td className="p-2 font-mono text-xs text-muted-foreground">{d.data}</td>
                <td className={cn(
                  "p-2 text-right font-mono",
                  d.valor < 0 ? "text-red-600" : "text-green-600"
                )}>
                  {formatBRL(d.valor)}
                </td>
                <td className="p-2 max-w-[280px]">
                  <div className="font-medium truncate" title={d.nome}>{d.nome || "—"}</div>
                  <div className="text-xs text-muted-foreground truncate" title={d.memo}>{d.memo}</div>
                </td>
                <td className="p-2">
                  <span className={cn("inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap", cx)}>
                    {d.disposicao}
                  </span>
                </td>
                <td className="p-2 text-xs">{d.contraparte || "—"}</td>
                <td className="p-2 text-xs text-muted-foreground font-mono">{d.origem || "—"}</td>
                <td className="p-2 text-xs text-muted-foreground max-w-[200px] truncate" title={d.flag ?? undefined}>
                  {d.flag || ""}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {disposicoes.length > 200 && (
        <p className="p-3 text-center text-xs text-muted-foreground border-t">
          Exibindo 200 de {disposicoes.length}.
        </p>
      )}
    </div>
  );
}
