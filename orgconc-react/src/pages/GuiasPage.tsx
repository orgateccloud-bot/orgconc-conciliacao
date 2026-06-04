import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  criarGuia,
  listarClientes,
  listarGuias,
  type Guia,
} from "@/lib/api";
import { HeroCard } from "@/components/HeroCard";
import { ListSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatBRLNum } from "@/lib/utils";
import { toast } from "sonner";
import { Receipt, Search } from "lucide-react";

const TIPOS = ["DARF", "DAS", "GPS", "GNRE", "DAE", "DARJ"];

const TIPO_CX: Record<string, string> = {
  DARF: "bg-blue-100 text-blue-700 border-blue-200",
  DAS:  "bg-green-100 text-green-700 border-green-200",
  GPS:  "bg-orange-100 text-orange-700 border-orange-200",
  GNRE: "bg-purple-100 text-purple-700 border-purple-200",
  DAE:  "bg-amber-100 text-amber-700 border-amber-200",
  DARJ: "bg-cyan-100 text-cyan-700 border-cyan-200",
};

export function GuiasPage() {
  const { data: clientes = [] } = useQuery({ queryKey: ["clientes"], queryFn: listarClientes });
  const [guias, setGuias] = useState<Guia[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");

  // Form de criação
  const [clienteId, setClienteId] = useState("");
  const [tipo, setTipo] = useState("DARF");
  const [valor, setValor] = useState("");
  const [competencia, setCompetencia] = useState("");
  const [vencimento, setVencimento] = useState("");
  const [contaContabil, setContaContabil] = useState("");
  const [busy, setBusy] = useState(false);

  async function carregar() {
    setLoading(true);
    try {
      const gs = await listarGuias();
      setGuias(gs);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { carregar(); }, []);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!clienteId || !valor) {
      toast.error("Preencha cliente e valor");
      return;
    }
    setBusy(true);
    try {
      const limpo = valor.replace(/[^0-9,]/g, "");
      const valorNum = Number(limpo.replace(",", "."));
      if (isNaN(valorNum) || valorNum <= 0) { toast.error("Valor inválido"); return; }
      await criarGuia({
        cliente_id: clienteId,
        tipo,
        valor: valorNum,
        competencia: competencia || null,
        data_vencimento: vencimento || null,
        conta_contabil: contaContabil || null,
      });
      toast.success("Guia cadastrada");
      setValor(""); setCompetencia(""); setVencimento(""); setContaContabil("");
      await carregar();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao cadastrar");
    } finally {
      setBusy(false);
    }
  }

  const guiasFiltradas = useMemo(() => {
    const q = busca.toLowerCase();
    if (!q) return guias;
    return guias.filter(
      (g) =>
        g.tipo.toLowerCase().includes(q) ||
        (g.competencia ?? "").toLowerCase().includes(q) ||
        String(g.valor).includes(q)
    );
  }, [guias, busca]);

  const nomePorId = useMemo(() => {
    const m: Record<string, string> = {};
    clientes.forEach((c) => { m[c.id] = c.nome; });
    return m;
  }, [clientes]);

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="MATCHERS · ESTÁGIO 4"
        title="Guias"
        titleAccent="tributárias."
        subtitle="DARF, DAS, GPS, GNRE. Cadastre e o matcher casa automaticamente com pagamentos no extrato."
      />

      <form onSubmit={salvar} className="rounded-3xl border glass p-6 space-y-4">
        <h3 className="font-semibold text-base">Nova guia</h3>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2 md:col-span-2">
            <Label>Cliente *</Label>
            <Select value={clienteId} onValueChange={setClienteId}>
              <SelectTrigger>
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent>
                {clientes.map((c) => (
                  <SelectItem key={c.id} value={c.id}>{c.nome}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Tipo *</Label>
            <Select value={tipo} onValueChange={setTipo}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {TIPOS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Valor (R$) *</Label>
            <Input value={valor} onChange={(e) => setValor(e.target.value)} placeholder="1234.56" required />
          </div>
          <div className="space-y-2">
            <Label>Competência</Label>
            <Input value={competencia} onChange={(e) => setCompetencia(e.target.value)} placeholder="2026-05" />
          </div>
          <div className="space-y-2">
            <Label>Vencimento</Label>
            <Input type="date" value={vencimento} onChange={(e) => setVencimento(e.target.value)} />
          </div>
          <div className="space-y-2 md:col-span-3">
            <Label>Conta contábil</Label>
            <Input value={contaContabil} onChange={(e) => setContaContabil(e.target.value)} placeholder="2.1.3.01.001" />
          </div>
        </div>
        <Button type="submit" disabled={busy}>{busy ? "Salvando…" : "Cadastrar guia"}</Button>
      </form>

      <div className="rounded-3xl border overflow-hidden">
        <div className="flex items-center gap-2 p-4 border-b bg-muted/30">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <Input
            placeholder="Buscar por tipo, competência ou valor…"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            className="h-8 border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 p-0"
          />
          <span className="text-xs text-muted-foreground shrink-0">{guiasFiltradas.length}</span>
        </div>
        {loading ? (
          <div className="p-6"><ListSkeleton items={3} /></div>
        ) : guiasFiltradas.length === 0 ? (
          <div className="p-12 flex flex-col items-center gap-3 text-center">
            <Receipt className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">Nenhuma guia cadastrada.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3 font-semibold">Tipo</th>
                <th className="text-left p-3 font-semibold">Cliente</th>
                <th className="text-right p-3 font-semibold">Valor (R$)</th>
                <th className="text-left p-3 font-semibold">Competência</th>
                <th className="text-left p-3 font-semibold">Vencimento</th>
                <th className="text-left p-3 font-semibold">Conta</th>
              </tr>
            </thead>
            <tbody>
              {guiasFiltradas.map((g) => (
                <tr key={g.id} className="border-t hover:bg-muted/30">
                  <td className="p-3">
                    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold ${TIPO_CX[g.tipo] ?? "bg-gray-100 text-gray-700"}`}>
                      {g.tipo}
                    </span>
                  </td>
                  <td className="p-3 text-xs">{nomePorId[g.cliente_id] ?? g.cliente_id.slice(0, 8)}</td>
                  <td className="p-3 text-right font-mono">{formatBRLNum(g.valor)}</td>
                  <td className="p-3 text-xs">{g.competencia ?? "—"}</td>
                  <td className="p-3 text-xs">{g.data_vencimento ?? "—"}</td>
                  <td className="p-3 text-xs font-mono">{g.conta_contabil ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
