import { useCallback, useEffect, useRef, useState } from "react";
import {
  fiscalLaudoResumo,
  gerarLaudoComFila,
  listarClientes,
  type Cliente,
  type FiscalAuditoriaResumo,
  type RegimeClasse,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ProgressBar } from "@/components/ui/progress-bar";
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
import {
  Upload,
  FileText,
  Scale,
  Gauge,
  AlertTriangle,
  Download,
  Flame,
  Repeat,
  Ban,
  Clock,
} from "lucide-react";
import { cn, formatBytes } from "@/lib/utils";

// Classe de compatibilidade de regime (regime_fiscal.py): múltiplo do teto.
const REGIME_BADGE: Record<RegimeClasse, string> = {
  COMPATIVEL: "bg-green-100 text-green-700 border-green-200",
  ATENCAO: "bg-blue-100 text-blue-700 border-blue-200",
  ALTO: "bg-orange-100 text-orange-700 border-orange-200",
  CRITICO: "bg-red-100 text-red-700 border-red-200",
};
const REGIME_TEXTO: Record<RegimeClasse, string> = {
  COMPATIVEL: "Volume anualizado dentro do teto do regime.",
  ATENCAO: "Volume anualizado acima do teto — verificar enquadramento.",
  ALTO: "Volume entre 3× e 10× o teto — forte indício de incompatibilidade.",
  CRITICO: "Volume acima de 10× o teto — indício nº 1 de caixa dois / interposição.",
};

const HEAT_COLOR: Record<string, string> = {
  CRITICO: "bg-red-500",
  ALTO: "bg-orange-500",
  MEDIO: "bg-blue-500",
  BAIXO: "bg-green-500",
};

function formatBRL(v: number): string {
  return v.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  });
}

function soDigitos(s: string): string {
  return s.replace(/\D/g, "");
}

export function AuditoriaForensePage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clienteId, setClienteId] = useState<string>("");
  const [cnpj, setCnpj] = useState<string>("");
  const [conta, setConta] = useState<string>("");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [baixando, setBaixando] = useState(false);
  const [resumo, setResumo] = useState<FiscalAuditoriaResumo | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => toast.error("Falha ao carregar clientes"));
  }, []);

  // Selecionar um cliente pré-preenche o CNPJ (editável).
  function onClienteChange(id: string) {
    setClienteId(id);
    const c = clientes.find((x) => x.id === id);
    if (c?.cnpj) setCnpj(c.cnpj);
  }

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    const todos = Array.from(list);
    const ofx = todos.filter((f) => f.name.toLowerCase().endsWith(".ofx"));
    if (ofx.length < todos.length) {
      toast.warning("Apenas arquivos .ofx são aceitos aqui.");
    }
    setArquivos((prev) => {
      const vistos = new Set(prev.map((f) => `${f.name}:${f.size}`));
      const novos = ofx.filter((f) => !vistos.has(`${f.name}:${f.size}`));
      return [...prev, ...novos].slice(0, 50);
    });
  }, []);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  }

  function validar(): boolean {
    if (soDigitos(cnpj).length !== 14) {
      toast.error("Informe o CNPJ da empresa auditada (14 dígitos).");
      return false;
    }
    if (!arquivos.length) {
      toast.error("Envie ao menos 1 extrato OFX.");
      return false;
    }
    return true;
  }

  async function analisar() {
    if (!validar()) return;
    setBusy(true);
    try {
      const r = await fiscalLaudoResumo(soDigitos(cnpj), conta.trim(), arquivos);
      setResumo(r);
      toast.success(
        `${r.n_transacoes} transações analisadas · regime ${r.regime.classe}`,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha na análise forense");
    } finally {
      setBusy(false);
    }
  }

  async function baixarLaudo() {
    if (!validar()) return;
    setBaixando(true);
    try {
      // Via fila de jobs (#122); fallback síncrono quando a fila não está
      // disponível (sem banco / token sem org).
      const { blob, filename } = await gerarLaudoComFila({
        empresaCnpj: soDigitos(cnpj),
        conta: conta.trim() || undefined,
        arquivos,
        formato: "xlsx",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "laudo.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Revoga em tick posterior: revogar síncrono após click() pode abortar
      // o download em alguns navegadores (Chromium/Safari).
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success("Laudo XLSX (11 abas) gerado.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao gerar o laudo");
    } finally {
      setBaixando(false);
    }
  }

  const heatTotal = resumo
    ? Object.values(resumo.heatmap).reduce((a, b) => a + b.qtd, 0)
    : 0;

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="FISCAL · AUDITORIA FORENSE"
        title="Regime ×"
        titleAccent="teto."
        subtitle="Metodologia OrgAudi sobre extratos OFX: anualiza o volume movimentado e compara com o teto do regime. Mostra heatmap de risco, sinais forenses (pós-baixa, smurfing, carrossel) e gera o laudo XLSX de 11 abas."
      />

      {/* Card de upload + parâmetros */}
      <section className="rounded-3xl border glass p-6 space-y-5">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label>Cliente (opcional)</Label>
            <Select value={clienteId} onValueChange={onClienteChange}>
              <SelectTrigger>
                <SelectValue placeholder="Preenche o CNPJ" />
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
          <div className="space-y-2">
            <Label>CNPJ da empresa auditada</Label>
            <input
              value={cnpj}
              onChange={(e) => setCnpj(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="00.000.000/0000-00"
            />
          </div>
          <div className="space-y-2">
            <Label>Conta (opcional)</Label>
            <input
              value={conta}
              onChange={(e) => setConta(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="Ex: 158083 (substring do ID)"
            />
          </div>
        </div>

        <div
          role="button"
          tabIndex={0}
          aria-label="Selecionar extratos OFX — Enter/Espaço ou clique; ou arraste e solte"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
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
            Arraste 1+ extratos <strong>.ofx</strong>
          </span>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".ofx"
            className="hidden"
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = ""; // permite re-selecionar o mesmo arquivo
            }}
          />
        </div>

        {arquivos.length > 0 && (
          <ul className="space-y-2 max-h-40 overflow-y-auto">
            {arquivos.map((f) => (
              <li key={`${f.name}:${f.size}`} className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm">
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate font-mono text-xs">{f.name}</span>
                <span className="text-xs text-muted-foreground">{formatBytes(f.size)}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <Button onClick={analisar} disabled={busy || baixando}>
            {busy ? "Analisando..." : "Analisar Regime × Teto"}
          </Button>
          <Button
            onClick={baixarLaudo}
            disabled={busy || baixando}
            variant="outline"
          >
            <Download className="h-4 w-4 mr-2" />
            {baixando ? "Gerando..." : "Baixar Laudo XLSX (11 abas)"}
          </Button>
        </div>
      </section>

      {resumo && (
        <>
          {/* Identificação da empresa */}
          <section className="rounded-3xl border bg-card p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <div className="text-lg font-bold">
                  {resumo.empresa.razao_social || "—"}
                </div>
                <div className="text-xs text-muted-foreground font-mono">
                  {resumo.empresa.cnpj}
                </div>
              </div>
              <div className="text-xs text-muted-foreground text-right">
                {resumo.periodo.inicio && resumo.periodo.fim && (
                  <div>
                    Período: {resumo.periodo.inicio} → {resumo.periodo.fim} ·{" "}
                    {resumo.meses_observados} meses
                  </div>
                )}
                <div>
                  {resumo.empresa.situacao} · porte {resumo.empresa.porte}
                  {resumo.conta && <> · conta {resumo.conta}</>}
                </div>
              </div>
            </div>
          </section>

          {/* Enriquecimento de CNPJ pendente → pós-baixa pode estar incompleta */}
          {resumo.enriquecimento_pendente > 0 && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900 px-4 py-3 flex items-start gap-3">
              <Clock className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-sm">
                <span className="font-semibold text-amber-700 dark:text-amber-400">
                  {resumo.enriquecimento_pendente} CNPJ(s) sendo enriquecidos em segundo plano.
                </span>{" "}
                <span className="text-muted-foreground">
                  Situação cadastral (pós-baixa) pode estar incompleta. Re-analise em alguns
                  minutos para o resultado fiel.
                </span>
              </div>
            </div>
          )}

          {/* Achado central: múltiplo do teto */}
          <section
            className={cn(
              "rounded-3xl border p-6",
              resumo.regime.incompativel
                ? "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-900"
                : "bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-900",
            )}
          >
            <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider mb-2">
              <Gauge className="h-4 w-4" /> Múltiplo do Teto (achado central)
            </div>
            <div className="flex flex-wrap items-end gap-4">
              <div
                className={cn(
                  "text-6xl font-bold",
                  resumo.regime.incompativel ? "text-red-600" : "text-green-700",
                )}
              >
                {resumo.regime.multiplo_do_teto.toLocaleString("pt-BR", {
                  maximumFractionDigits: 1,
                })}
                ×
              </div>
              <span
                className={cn(
                  "inline-block px-3 py-1 rounded-lg text-sm font-semibold border mb-2",
                  REGIME_BADGE[resumo.regime.classe],
                )}
              >
                {resumo.regime.classe}
              </span>
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              {REGIME_TEXTO[resumo.regime.classe]}
            </p>
          </section>

          {/* Volume / anualizado / teto */}
          <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-3xl border bg-card p-5">
              <div className="text-muted-foreground text-xs uppercase tracking-wider">
                Volume Bruto (período)
              </div>
              <div className="text-2xl font-bold mt-2">
                {formatBRL(resumo.regime.volume_bruto)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {resumo.n_transacoes} transações
              </div>
            </div>
            <div className="rounded-3xl border bg-card p-5">
              <div className="text-muted-foreground text-xs uppercase tracking-wider">
                Volume Anualizado
              </div>
              <div className="text-2xl font-bold mt-2 text-orange-600">
                {formatBRL(resumo.regime.volume_anualizado)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                projeção 12 meses
              </div>
            </div>
            <div className="rounded-3xl border bg-card p-5">
              <div className="text-muted-foreground text-xs uppercase tracking-wider">
                Teto do Regime
              </div>
              <div className="text-2xl font-bold mt-2">
                {formatBRL(resumo.regime.teto)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">LC 123/2006</div>
            </div>
          </section>

          {/* Heatmap por classe de risco */}
          <section className="rounded-3xl border glass p-6">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Scale className="h-5 w-5" />
              Heatmap de Risco por Transação
            </h2>
            <div className="space-y-3">
              {(["CRITICO", "ALTO", "MEDIO", "BAIXO"] as const).map((classe) => {
                const cell = resumo.heatmap[classe] ?? { qtd: 0, volume: 0 };
                const pct = heatTotal > 0 ? (cell.qtd / heatTotal) * 100 : 0;
                return (
                  <div key={classe}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="font-medium">
                        {classe}{" "}
                        <span className="text-muted-foreground">
                          ({cell.qtd} tx)
                        </span>
                      </span>
                      <span className="font-mono">{formatBRL(cell.volume)}</span>
                    </div>
                    <ProgressBar value={pct} colorClass={HEAT_COLOR[classe]} label={`${classe}: ${pct.toFixed(1)}% (${cell.qtd} tx)`} />
                  </div>
                );
              })}
            </div>
          </section>

          {/* Sinais forenses + retenção */}
          <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-3xl border bg-card p-5">
              <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
                <Ban className="h-4 w-4" /> Pós-baixa
              </div>
              <div className="text-3xl font-bold mt-2 text-red-600">
                {resumo.sinais.pos_baixa}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                pagamentos após baixa do CNPJ
              </div>
            </div>
            <div className="rounded-3xl border bg-card p-5">
              <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
                <Flame className="h-4 w-4" /> Smurfing
              </div>
              <div className="text-3xl font-bold mt-2 text-orange-600">
                {resumo.sinais.smurfing}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                fracionamento &lt; R$ 10k
              </div>
            </div>
            <div className="rounded-3xl border bg-card p-5">
              <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
                <Repeat className="h-4 w-4" /> Carrossel
              </div>
              <div className="text-3xl font-bold mt-2 text-orange-600">
                {resumo.sinais.carrossel}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                crédito + débito mesma parte
              </div>
            </div>
            <div className="rounded-3xl border bg-card p-5">
              <div className="text-muted-foreground text-xs uppercase tracking-wider">
                Retenção Estimada
              </div>
              <div className="text-2xl font-bold mt-2">
                {formatBRL(resumo.retencao_estimada)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                na fonte (período)
              </div>
            </div>
          </section>

          {/* Top disposições */}
          {resumo.top_disposicoes.length > 0 && (
            <section className="rounded-3xl border glass p-6">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-600" />
                Top Disposições por Risk Score
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="py-2 px-2">Data</th>
                      <th className="py-2 px-2">CNPJ</th>
                      <th className="py-2 px-2 text-right">Valor</th>
                      <th className="py-2 px-2">Meio</th>
                      <th className="py-2 px-2 text-right">Score</th>
                      <th className="py-2 px-2">Classe</th>
                      <th className="py-2 px-2">Sinais</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resumo.top_disposicoes.map((d, i) => (
                      <tr key={i} className="border-b hover:bg-muted/30">
                        <td className="py-2 px-2 whitespace-nowrap">{d.data?.slice(0, 10)}</td>
                        <td className="py-2 px-2 font-mono text-xs">{d.cnpj || "—"}</td>
                        <td className="py-2 px-2 text-right font-semibold">
                          {formatBRL(d.valor)}
                        </td>
                        <td className="py-2 px-2 text-xs">{d.meio}</td>
                        <td className="py-2 px-2 text-right font-mono">{d.risk_score}</td>
                        <td className="py-2 px-2">
                          <span className={cn(
                            "inline-block px-2 py-0.5 rounded text-xs font-semibold text-white",
                            HEAT_COLOR[d.risco_classe] ?? "bg-gray-400",
                          )}>
                            {d.risco_classe}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-xs text-muted-foreground">
                          {d.sinais.join(", ") || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
