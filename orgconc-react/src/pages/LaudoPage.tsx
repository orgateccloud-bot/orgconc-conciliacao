import { useCallback, useRef, useState } from "react";
import { fiscalLaudo, baixarBlob, type FormatoLaudo } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { HeroCard } from "@/components/HeroCard";
import { toast } from "sonner";
import { FileText, Upload, FileSpreadsheet, FileCode, FileDown } from "lucide-react";
import { cn, formatBytes } from "@/lib/utils";

const FORMATOS: { id: FormatoLaudo; label: string; icon: typeof FileText; hint: string }[] = [
  { id: "xlsx", label: "XLSX", icon: FileSpreadsheet, hint: "Planilha (13 abas)" },
  { id: "pdf", label: "PDF", icon: FileDown, hint: "Documento para imprimir" },
  { id: "html", label: "HTML", icon: FileCode, hint: "Visualizar no navegador" },
];

export function LaudoPage() {
  const [empresaCnpj, setEmpresaCnpj] = useState("");
  const [conta, setConta] = useState("");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [formato, setFormato] = useState<FormatoLaudo>("xlsx");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    setArquivos((prev) => [...prev, ...Array.from(list)].slice(0, 200));
  }, []);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  }

  function removeFile(i: number) {
    setArquivos((prev) => prev.filter((_, idx) => idx !== i));
  }

  const temOfx = arquivos.some((f) => f.name.toLowerCase().endsWith(".ofx"));
  const temFiscal = arquivos.some(
    (f) => f.name.toLowerCase().endsWith(".xml") || f.name.toLowerCase().endsWith(".zip"),
  );
  const cnpjLimpo = empresaCnpj.replace(/\D/g, "");

  async function gerar() {
    if (cnpjLimpo.length !== 14) {
      toast.error("Informe o CNPJ da entidade auditada (14 dígitos)");
      return;
    }
    if (!temOfx) {
      toast.error("Envie ao menos 1 extrato OFX");
      return;
    }
    setBusy(true);
    try {
      const { blob, filename } = await fiscalLaudo({
        empresaCnpj: cnpjLimpo,
        conta: conta.trim() || undefined,
        arquivos,
        formato,
      });
      if (formato === "html") {
        // abre o HTML numa nova aba além de baixar
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      } else {
        baixarBlob(blob, filename);
      }
      toast.success(`Laudo gerado: ${filename}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao gerar laudo");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="LAUDO · AUDITORIA INTEGRADA"
        title="Laudo Integrado"
        titleAccent="forense."
        subtitle="Gera o laudo de auditoria bancária a partir de extratos OFX. Anexe ZIPs/XMLs de NF-e/CT-e para incluir as seções fiscais (Documentos Fiscais + Conformidade) no mesmo documento."
      />

      <section className="rounded-3xl border glass p-6 space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="cnpj">CNPJ da entidade auditada</Label>
            <Input
              id="cnpj"
              placeholder="00.000.000/0000-00"
              value={empresaCnpj}
              onChange={(e) => setEmpresaCnpj(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="conta">Conta (opcional)</Label>
            <Input
              id="conta"
              placeholder="substring do ID da conta no OFX (ex: 158083)"
              value={conta}
              onChange={(e) => setConta(e.target.value)}
            />
          </div>
        </div>

        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOver(false);
          }}
          onDrop={onDrop}
          className={cn(
            "flex flex-col items-center justify-center border-2 border-dashed rounded-2xl p-10 cursor-pointer transition-all select-none",
            dragOver ? "border-primary bg-primary/5 scale-[1.01]" : "hover:bg-muted/30 hover:border-primary/50",
          )}
        >
          <Upload className={cn("h-8 w-8 mb-2 transition-colors", dragOver ? "text-primary" : "text-muted-foreground")} />
          <span className="text-sm text-muted-foreground text-center">
            Arraste os <strong>extratos OFX</strong> + (opcional) <strong>ZIPs/XMLs</strong> de NF-e/CT-e
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
          <>
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span className={cn(temOfx ? "text-emerald-600 font-medium" : "")}>
                OFX: {arquivos.filter((f) => f.name.toLowerCase().endsWith(".ofx")).length}
              </span>
              <span className={cn(temFiscal ? "text-primary font-medium" : "")}>
                Fiscais (XML/ZIP): {arquivos.filter((f) => /\.(xml|zip)$/i.test(f.name)).length}
              </span>
            </div>
            <ul className="space-y-2 max-h-40 overflow-y-auto">
              {arquivos.map((f, i) => (
                <li key={i} className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1 truncate font-mono text-xs">{f.name}</span>
                  <span className="text-xs text-muted-foreground">{formatBytes(f.size)}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(i);
                    }}
                    className="text-xs text-muted-foreground hover:text-red-600"
                    aria-label="Remover arquivo"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}

        <div className="space-y-2">
          <Label>Formato</Label>
          <div className="grid grid-cols-3 gap-3">
            {FORMATOS.map(({ id, label, icon: Icon, hint }) => (
              <button
                key={id}
                onClick={() => setFormato(id)}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-xl border p-4 transition-all",
                  formato === id
                    ? "border-primary bg-primary/5 ring-1 ring-primary"
                    : "hover:bg-muted/30 hover:border-primary/50",
                )}
              >
                <Icon className={cn("h-5 w-5", formato === id ? "text-primary" : "text-muted-foreground")} />
                <span className="text-sm font-semibold">{label}</span>
                <span className="text-[10px] text-muted-foreground text-center">{hint}</span>
              </button>
            ))}
          </div>
        </div>

        <Button onClick={gerar} disabled={busy} className="w-full">
          {busy ? "Gerando laudo..." : `Gerar Laudo (${formato.toUpperCase()})`}
        </Button>

        {temFiscal && (
          <p className="text-xs text-muted-foreground text-center">
            Documentos fiscais detectados — o laudo incluirá as seções 12. Documentos Fiscais e 13. Conformidade Fiscal.
          </p>
        )}
      </section>
    </div>
  );
}
