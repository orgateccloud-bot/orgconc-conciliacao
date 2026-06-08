import { useEffect, useState } from "react";
import {
  fiscalRiscoTributario,
  listarClientes,
  type Cliente,
  type FiscalRiscoResponse,
} from "@/lib/api";
import { Label } from "@/components/ui/label";
import { ProgressBar } from "@/components/ui/progress-bar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { HeroCard } from "@/components/HeroCard";
import { toast } from "sonner";
import { cn, formatBRL } from "@/lib/utils";
import { corBadge, CLASSE_COLOR_BAR } from "@/lib/risco-cores";
import { Calculator, AlertTriangle, Scale } from "lucide-react";

export function RiscoTributarioPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clienteId, setClienteId] = useState<string>("");
  const [risco, setRisco] = useState<FiscalRiscoResponse | null>(null);
  const [simulValor, setSimulValor] = useState<number>(0);

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => toast.error("Falha ao carregar clientes"));
  }, []);

  useEffect(() => {
    if (!clienteId) {
      setRisco(null);
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fiscalRiscoTributario(clienteId);
        if (!cancelled) setRisco(r);
      } catch (e) {
        if (!cancelled)
          toast.error(e instanceof Error ? e.message : "Falha ao carregar risco");
      }
    };
    load();
    return () => { cancelled = true; };
  }, [clienteId]);

  const totalClasse = risco
    ? Object.values(risco.por_classe_risco).reduce((a, b) => a + b, 0)
    : 0;

  const economiaEstimada = simulValor * 0.34;

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="FISCAL · RISCO TRIBUTÁRIO"
        title="Risco em"
        titleAccent="Lucro Real."
        subtitle="Estimativa anual de IRPJ + CSLL (34%) sobre despesa indedutível e retenções não recolhidas. Inclui simulador de economia ao regularizar NF-es."
      />

      <section className="rounded-3xl border glass p-6 space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Cliente</Label>
            <Select value={clienteId} onValueChange={setClienteId}>
              <SelectTrigger>
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent>
                {clientes.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.nome}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </section>

      {risco && (
        <>
          {/* Totais */}
          <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-3xl border bg-card p-5">
              <div className="text-muted-foreground text-xs uppercase tracking-wider">
                Risco Total Anual
              </div>
              <div className="text-3xl font-bold mt-2 text-red-600">
                {formatBRL(risco.risco_total_anual)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {risco.regime_pressuposto} · {risco.aliquota_aplicada_pct}% IRPJ+CSLL
              </div>
            </div>
            <div className="rounded-3xl border bg-card p-5">
              <div className="text-muted-foreground text-xs uppercase tracking-wider">
                Despesa Indedutível
              </div>
              <div className="text-3xl font-bold mt-2 text-orange-600">
                {formatBRL(risco.risco_despesa_indedutivel_anual)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">RIR/2018 art. 311</div>
            </div>
            <div className="rounded-3xl border bg-card p-5">
              <div className="text-muted-foreground text-xs uppercase tracking-wider">
                Retenções Não Recolhidas
              </div>
              <div className="text-3xl font-bold mt-2 text-orange-600">
                {formatBRL(risco.risco_retencoes_anual)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                PIS+COFINS+CSLL+IRRF (6,15%)
              </div>
            </div>
          </section>

          {/* Distribuição por classe */}
          <section className="rounded-3xl border glass p-6">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Scale className="h-5 w-5" />
              Distribuição por Classe de Risco
            </h2>
            <div className="space-y-3">
              {(["CRITICO", "ALTO", "MEDIO", "BAIXO"] as const).map((classe) => {
                const valor = risco.por_classe_risco[classe] ?? 0;
                const pct = totalClasse > 0 ? (valor / totalClasse) * 100 : 0;
                const cnt = risco.contagem_fornecedores[classe] ?? 0;
                return (
                  <div key={classe}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="font-medium">
                        {classe} <span className="text-muted-foreground">({cnt} fornec.)</span>
                      </span>
                      <span className="font-mono">{formatBRL(valor)}</span>
                    </div>
                    <ProgressBar value={pct} colorClass={CLASSE_COLOR_BAR[classe]} />
                  </div>
                );
              })}
            </div>
          </section>

          {/* Top 10 fornecedores */}
          {risco.top_10_fornecedores.length > 0 && (
            <section className="rounded-3xl border glass p-6">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-600" />
                Top 10 Fornecedores por Risco
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="py-2 px-2">#</th>
                      <th className="py-2 px-2">Fornecedor</th>
                      <th className="py-2 px-2">CNPJ</th>
                      <th className="py-2 px-2">Classe</th>
                      <th className="py-2 px-2 text-right">Risco Anual</th>
                      <th className="py-2 px-2">Flags</th>
                    </tr>
                  </thead>
                  <tbody>
                    {risco.top_10_fornecedores.map((f, i) => (
                      <tr key={f.cnpj} className="border-b hover:bg-muted/30">
                        <td className="py-2 px-2">{i + 1}</td>
                        <td className="py-2 px-2 font-medium">{f.razao_social || "—"}</td>
                        <td className="py-2 px-2 font-mono text-xs">{f.cnpj}</td>
                        <td className="py-2 px-2">
                          <span className={cn(
                            "inline-block px-2 py-0.5 rounded text-xs font-semibold text-white",
                            corBadge(f.classe),
                          )}>
                            {f.classe}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-right font-semibold text-red-600">
                          {formatBRL(f.risco_anual)}
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

          {/* Simulador */}
          <section className="rounded-3xl border glass p-6">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Calculator className="h-5 w-5" />
              Simulador de Economia
            </h2>
            <p className="text-sm text-muted-foreground mb-4">
              Se eu cadastrar NF-e para fornecedor X no valor abaixo, quanto economizo de
              IRPJ + CSLL?
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Valor da NF-e a regularizar (R$/ano)</Label>
                <input
                  type="number"
                  value={simulValor}
                  onChange={(e) => setSimulValor(Number(e.target.value) || 0)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  placeholder="Ex: 1000000"
                />
              </div>
              <div className="rounded-xl bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 p-4">
                <div className="text-muted-foreground text-xs uppercase tracking-wider">
                  Economia Estimada/Ano
                </div>
                <div className="text-3xl font-bold mt-1 text-green-700 dark:text-green-400">
                  {formatBRL(economiaEstimada)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Base × 34% (IRPJ 25% + CSLL 9%)
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  * Baseado em Lucro Real (IRPJ+CSLL 34%). Simples Nacional: ~6-33%; Lucro Presumido: ~15-24%.
                </p>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
