import { useCallback, useEffect, useState } from "react";
import {
  fiscalGerarCarta,
  fiscalListarCartas,
  listarClientes,
  type Cliente,
  type FiscalCartaItem,
  type FiscalCartaResponse,
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
import { FileText, Download, RefreshCw } from "lucide-react";

function formatBRL(v: number): string {
  return v.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  });
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR");
}

export function CartasFiscaisPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clienteId, setClienteId] = useState<string>("");
  const [cartas, setCartas] = useState<FiscalCartaItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [ultimaGerada, setUltimaGerada] = useState<FiscalCartaResponse | null>(null);

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => toast.error("Falha ao carregar clientes"));
  }, []);

  const loadCartas = useCallback(async () => {
    if (!clienteId) {
      setCartas([]);
      return;
    }
    try {
      const r = await fiscalListarCartas(clienteId);
      setCartas(r.cartas);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao listar cartas");
    }
  }, [clienteId]);

  useEffect(() => {
    loadCartas();
  }, [loadCartas]);

  async function gerarCarta() {
    if (!clienteId) {
      toast.error("Selecione um cliente");
      return;
    }
    setBusy(true);
    try {
      const r = await fiscalGerarCarta(clienteId);
      setUltimaGerada(r);
      toast.success(`Carta ${r.versao} gerada — ${r.total_fornecedores} fornecedores`);
      await loadCartas();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao gerar carta");
    } finally {
      setBusy(false);
    }
  }

  function downloadPdf() {
    if (!ultimaGerada?.pdf_base64) return;
    const byteCharacters = atob(ultimaGerada.pdf_base64);
    const byteArray = new Uint8Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteArray[i] = byteCharacters.charCodeAt(i);
    }
    const blob = new Blob([byteArray], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Carta_${ultimaGerada.cliente_nome.replace(/[^a-z0-9]+/gi, "_")}_${ultimaGerada.versao}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="FISCAL · CARTAS AUTO"
        title="Cartas de constatação"
        titleAccent="auto-geradas."
        subtitle="Geração automática a partir dos dados de conformidade do cliente. Cada versão fica versionada com hash de integridade."
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
          <div className="flex items-end gap-2">
            <Button onClick={gerarCarta} disabled={busy} className="flex-1">
              <FileText className="h-4 w-4 mr-2" />
              {busy ? "Gerando..." : "Gerar Nova Carta"}
            </Button>
            <Button variant="outline" onClick={loadCartas} disabled={busy}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {ultimaGerada && (
          <div className="rounded-xl bg-primary/5 border border-primary/20 px-4 py-3">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold text-sm">
                Carta {ultimaGerada.versao} gerada com sucesso
              </div>
              {ultimaGerada.pdf_base64 && (
                <Button size="sm" onClick={downloadPdf} variant="outline">
                  <Download className="h-4 w-4 mr-1" />
                  Baixar PDF
                </Button>
              )}
            </div>
            <div className="text-xs text-muted-foreground">
              Cliente: {ultimaGerada.cliente_nome} · Risco total:{" "}
              {formatBRL(ultimaGerada.risco_total)} · Fornecedores:{" "}
              {ultimaGerada.total_fornecedores}
            </div>
            <div className="text-xs text-muted-foreground mt-1 font-mono">
              Hash: {ultimaGerada.payload_hash.slice(0, 24)}...
            </div>
          </div>
        )}
      </section>

      {cartas.length > 0 && (
        <section className="rounded-3xl border glass p-6">
          <h2 className="text-lg font-bold mb-4">Histórico de Versões</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="py-2 px-2">#</th>
                  <th className="py-2 px-2">Versão</th>
                  <th className="py-2 px-2">Gerada em</th>
                  <th className="py-2 px-2 text-right">Risco Total</th>
                  <th className="py-2 px-2 text-right">Fornecedores</th>
                  <th className="py-2 px-2">Hash</th>
                </tr>
              </thead>
              <tbody>
                {cartas.map((c, i) => (
                  <tr key={c.id} className="border-b hover:bg-muted/30">
                    <td className="py-2 px-2">{i + 1}</td>
                    <td className="py-2 px-2 font-mono">{c.versao}</td>
                    <td className="py-2 px-2">{formatDate(c.gerado_em)}</td>
                    <td className="py-2 px-2 text-right">{formatBRL(c.risco_total)}</td>
                    <td className="py-2 px-2 text-right">{c.total_fornecedores}</td>
                    <td className="py-2 px-2 font-mono text-xs">
                      {c.payload_hash.slice(0, 16)}...
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
