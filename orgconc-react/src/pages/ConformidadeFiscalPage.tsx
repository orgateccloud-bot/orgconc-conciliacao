import { useCallback, useEffect, useRef, useState } from "react";
import {
  fiscalConformidade,
  fiscalProcessar,
  fiscalRiscoTributario,
  listarClientes,
  type Cliente,
  type FiscalConformidadeResponse,
  type FiscalProcessarResponse,
  type FiscalRiscoResponse,
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
import { FileText, Upload, ShieldCheck, AlertOctagon, TrendingDown, FileWarning } from "lucide-react";
import { cn } from "@/lib/utils";

const CLASSE_COLOR: Record<string, string> = {
  BAIXO: "bg-green-100 text-green-700 border-green-200",
  MEDIO: "bg-blue-100 text-blue-700 border-blue-200",
  ALTO: "bg-orange-100 text-orange-700 border-orange-200",
  CRITICO: "bg-red-100 text-red-700 border-red-200",
};

function formatBRL(v: number): string {
  return v.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  });
}

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

export function ConformidadeFiscalPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clienteId, setClienteId] = useState<string>("");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resultado, setResultado] = useState<FiscalProcessarResponse | null>(null);
  const [conformidade, setConformidade] = useState<FiscalConformidadeResponse | null>(null);
  const [risco, setRisco] = useState<FiscalRiscoResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => toast.error("Falha ao carregar clientes"));
  }, []);

  const loadDados = useCallback(async (cid: string) => {
    try {
      const [c, r] = await Promise.all([
        fiscalConformidade(cid),
        fiscalRiscoTributario(cid),
      ]);
      setConformidade(c);
      setRisco(r);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao carregar conformidade");
    }
  }, []);

  useEffect(() => {
    if (clienteId) loadDados(clienteId);
  }, [clienteId, loadDados]);

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    const news = Array.from(list).slice(0, 100);
    setArquivos((prev) => [...prev, ...news].slice(0, 200));
  }, []);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  }

  async function processar() {
    if (!clienteId) {
      toast.error("Selecione um cliente");
      return;
    }
    if (!arquivos.length) {
      toast.error("Envie ao menos 1 ZIP com NF-es/CT-es");
      return;
    }
    setBusy(true);
    try {
      const r = await fiscalProcessar(clienteId, arquivos);
      setResultado(r);
      toast.success(
        `${r.documentos_processados} documentos processados (${r.fornecedores_classificados} fornecedores classificados)`,
      );
      await loadDados(clienteId);
      setArquivos([]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro no processamento fiscal");
    } finally {
      setBusy(false);
    }
  }

  const scoreGeral = conformidade && conformidade.fornecedores.length
    ? Math.round(
        conformidade.fornecedores.reduce((acc, f) => acc + f.conformidade_pct, 0) /
          conformidade.fornecedores.length,
      )
    : 0;

  const volumeComNF = conformidade?.fornecedores.reduce((acc, f) => acc + f.volume_nf, 0) ?? 0;
  const volumeSemNF = conformidade?.fornecedores.reduce(
    (acc, f) => acc + Math.max(0, f.volume_pago - f.volume_nf),
    0,
  ) ?? 0;
  const topGap = (conformidade?.fornecedores ?? [])
    .filter((f) => f.risco_classe === "CRITICO" || f.risco_classe === "ALTO")
    .slice(0, 10);

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="FISCAL · CONFORMIDADE"
        title="Auditoria fiscal"
        titleAccent="cruzada."
        subtitle="Cruza NF-e/CT-e/NFS-e com pagamentos bancários. Identifica gaps fiscais e estima risco IRPJ+CSLL em Lucro Real."
      />

      {/* Card de upload */}
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
              : "hover:bg-muted/30 hover:border-primary/50",
          )}
        >
          <Upload className={cn("h-8 w-8 mb-2 transition-colors", dragOver ? "text-primary" : "text-muted-foreground")} />
          <span className="text-sm text-muted-foreground text-center">
            Arraste ZIPs de NF-e + CT-e + (opcional) OFX
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
          <ul className="space-y-2 max-h-40 overflow-y-auto">
            {arquivos.map((f, i) => (
              <li key={i} className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm">
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate font-mono text-xs">{f.name}</span>
                <span className="text-xs text-muted-foreground">{formatBytes(f.size)}</span>
              </li>
            ))}
          </ul>
        )}

        <Button onClick={processar} disabled={busy} className="w-full">
          {busy ? "Processando..." : "Iniciar Cruzamento Fiscal"}
        </Button>

        {resultado && (
          <div className="rounded-xl bg-primary/5 border border-primary/20 px-4 py-3 text-sm">
            <div className="font-semibold mb-1">Último processamento:</div>
            <div>
              <strong>{resultado.documentos_processados}</strong> documentos · NF-e: {resultado.documentos_por_tipo["NF-e"] ?? 0} · CT-e: {resultado.documentos_por_tipo["CT-e"] ?? 0} · NFS-e: {resultado.documentos_por_tipo["NFS-e"] ?? 0}
            </div>
            {resultado.cruzamentos && (
              <div className="text-muted-foreground mt-1">
                Cruzamentos: {resultado.cruzamentos.total} ·{" "}
                CASADO {resultado.cruzamentos.por_status["CASADO"] ?? 0} ·{" "}
                SEM_NF {resultado.cruzamentos.por_status["SEM_NF"] ?? 0} ·{" "}
                VALOR_DIVERGENTE {resultado.cruzamentos.por_status["VALOR_DIVERGENTE"] ?? 0}
              </div>
            )}
          </div>
        )}
      </section>

      {/* KPIs */}
      {conformidade && conformidade.fornecedores.length > 0 && (
        <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="rounded-3xl border bg-card p-5">
            <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
              <ShieldCheck className="h-4 w-4" /> Score Geral
            </div>
            <div className="text-4xl font-bold mt-2">{scoreGeral}%</div>
            <div className="text-xs text-muted-foreground mt-1">
              {conformidade.total} fornecedores
            </div>
          </div>
          <div className="rounded-3xl border bg-card p-5">
            <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
              <FileText className="h-4 w-4" /> Volume com NF
            </div>
            <div className="text-2xl font-bold mt-2">{formatBRL(volumeComNF)}</div>
          </div>
          <div className="rounded-3xl border bg-card p-5">
            <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
              <FileWarning className="h-4 w-4" /> Volume sem NF
            </div>
            <div className="text-2xl font-bold mt-2 text-red-600">{formatBRL(volumeSemNF)}</div>
          </div>
          <div className="rounded-3xl border bg-card p-5">
            <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
              <TrendingDown className="h-4 w-4" /> Risco Tributário/Ano
            </div>
            <div className="text-2xl font-bold mt-2 text-red-600">
              {risco ? formatBRL(risco.risco_total_anual) : "—"}
            </div>
            {risco && (
              <div className="text-xs text-muted-foreground mt-1">
                {risco.regime_pressuposto} · {risco.aliquota_aplicada_pct}%
              </div>
            )}
          </div>
        </section>
      )}

      {/* Top fornecedores com gap */}
      {topGap.length > 0 && (
        <section className="rounded-3xl border glass p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <AlertOctagon className="h-5 w-5 text-red-600" />
              Top Fornecedores com Gap Fiscal
            </h2>
            <span className="text-xs text-muted-foreground">
              Classe ALTO ou CRITICO
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="py-2 px-2">#</th>
                  <th className="py-2 px-2">Fornecedor</th>
                  <th className="py-2 px-2">CNPJ</th>
                  <th className="py-2 px-2 text-right">Pago</th>
                  <th className="py-2 px-2 text-right">NF</th>
                  <th className="py-2 px-2 text-right">Conformidade</th>
                  <th className="py-2 px-2 text-right">Risco/Ano</th>
                  <th className="py-2 px-2">Classe</th>
                  <th className="py-2 px-2">Flags</th>
                </tr>
              </thead>
              <tbody>
                {topGap.map((f, i) => (
                  <tr key={f.cnpj} className="border-b hover:bg-muted/30">
                    <td className="py-2 px-2">{i + 1}</td>
                    <td className="py-2 px-2 font-medium">{f.razao_social || "—"}</td>
                    <td className="py-2 px-2 font-mono text-xs">{f.cnpj}</td>
                    <td className="py-2 px-2 text-right">{formatBRL(f.volume_pago)}</td>
                    <td className="py-2 px-2 text-right">{formatBRL(f.volume_nf)}</td>
                    <td className="py-2 px-2 text-right">{f.conformidade_pct.toFixed(1)}%</td>
                    <td className="py-2 px-2 text-right font-semibold text-red-600">
                      {formatBRL(f.risco_tributario_anual)}
                    </td>
                    <td className="py-2 px-2">
                      <span className={cn(
                        "inline-block px-2 py-0.5 rounded text-xs font-semibold border",
                        CLASSE_COLOR[f.risco_classe] ?? "",
                      )}>
                        {f.risco_classe}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-xs text-muted-foreground">
                      {f.flags.join(", ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
