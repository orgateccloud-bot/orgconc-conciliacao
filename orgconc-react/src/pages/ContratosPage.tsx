import { useEffect, useMemo, useState } from "react";
import {
  criarContrato,
  listarClientes,
  listarContratos,
  type Cliente,
  type Contrato,
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
import { toast } from "sonner";
import { FileSignature, Search } from "lucide-react";

const PERIODICIDADES = ["mensal", "bimestral", "trimestral", "semestral", "anual"];

function formatBRL(v: number): string {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function ContratosPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [contratos, setContratos] = useState<Contrato[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");

  // Form
  const [clienteId, setClienteId] = useState("");
  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState("");
  const [periodicidade, setPeriodicidade] = useState("mensal");
  const [padraoMemo, setPadraoMemo] = useState("");
  const [contaContabil, setContaContabil] = useState("");
  const [busy, setBusy] = useState(false);

  async function carregar() {
    setLoading(true);
    try {
      const [cls, cs] = await Promise.all([listarClientes(), listarContratos()]);
      setClientes(cls);
      setContratos(cs);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { carregar(); }, []);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!clienteId || !descricao || !valor) {
      toast.error("Preencha cliente, descrição e valor");
      return;
    }
    setBusy(true);
    try {
      await criarContrato({
        cliente_id: clienteId,
        descricao,
        valor: Number(valor.replace(",", ".")),
        periodicidade,
        padrao_memo: padraoMemo || null,
        conta_contabil: contaContabil || null,
      });
      toast.success("Contrato cadastrado");
      setDescricao(""); setValor(""); setPadraoMemo(""); setContaContabil("");
      await carregar();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao cadastrar");
    } finally {
      setBusy(false);
    }
  }

  const contratosFiltrados = useMemo(() => {
    const q = busca.toLowerCase();
    if (!q) return contratos;
    return contratos.filter(
      (c) => c.descricao.toLowerCase().includes(q) || String(c.valor).includes(q)
    );
  }, [contratos, busca]);

  const nomePorId = useMemo(() => {
    const m: Record<string, string> = {};
    clientes.forEach((c) => { m[c.id] = c.nome; });
    return m;
  }, [clientes]);

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="MATCHERS · ESTÁGIO 5"
        title="Contratos"
        titleAccent="recorrentes."
        subtitle="Aluguel, seguro, leasing, consórcio. Valor fixo periódico que casa por valor + padrão no MEMO bancário."
      />

      <form onSubmit={salvar} className="rounded-3xl border glass p-6 space-y-4">
        <h3 className="font-semibold text-base">Novo contrato</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Cliente *</Label>
            <Select value={clienteId} onValueChange={setClienteId}>
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                {clientes.map((c) => <SelectItem key={c.id} value={c.id}>{c.nome}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Descrição *</Label>
            <Input value={descricao} onChange={(e) => setDescricao(e.target.value)} placeholder="Seguro frota" required />
          </div>
          <div className="space-y-2">
            <Label>Valor (R$) *</Label>
            <Input value={valor} onChange={(e) => setValor(e.target.value)} placeholder="780.00" required />
          </div>
          <div className="space-y-2">
            <Label>Periodicidade</Label>
            <Select value={periodicidade} onValueChange={setPeriodicidade}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {PERIODICIDADES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label>Padrão no MEMO (para desempate)</Label>
            <Input value={padraoMemo} onChange={(e) => setPadraoMemo(e.target.value)} placeholder="SEGURO" />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label>Conta contábil</Label>
            <Input value={contaContabil} onChange={(e) => setContaContabil(e.target.value)} placeholder="3.1.2.04.005" />
          </div>
        </div>
        <Button type="submit" disabled={busy}>{busy ? "Salvando…" : "Cadastrar contrato"}</Button>
      </form>

      <div className="rounded-3xl border overflow-hidden">
        <div className="flex items-center gap-2 p-4 border-b bg-muted/30">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <Input
            placeholder="Buscar por descrição ou valor…"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            className="h-8 border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 p-0"
          />
          <span className="text-xs text-muted-foreground shrink-0">{contratosFiltrados.length}</span>
        </div>
        {loading ? (
          <div className="p-6"><ListSkeleton items={3} /></div>
        ) : contratosFiltrados.length === 0 ? (
          <div className="p-12 flex flex-col items-center gap-3 text-center">
            <FileSignature className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">Nenhum contrato cadastrado.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3 font-semibold">Descrição</th>
                <th className="text-left p-3 font-semibold">Cliente</th>
                <th className="text-right p-3 font-semibold">Valor (R$)</th>
                <th className="text-left p-3 font-semibold">Periodicidade</th>
                <th className="text-left p-3 font-semibold">Padrão MEMO</th>
                <th className="text-left p-3 font-semibold">Conta</th>
              </tr>
            </thead>
            <tbody>
              {contratosFiltrados.map((c) => (
                <tr key={c.id} className="border-t hover:bg-muted/30">
                  <td className="p-3 font-medium">{c.descricao}</td>
                  <td className="p-3 text-xs">{nomePorId[c.cliente_id] ?? c.cliente_id.slice(0, 8)}</td>
                  <td className="p-3 text-right font-mono">{formatBRL(c.valor)}</td>
                  <td className="p-3 text-xs">{c.periodicidade ?? "—"}</td>
                  <td className="p-3 text-xs font-mono">{c.padrao_memo ?? "—"}</td>
                  <td className="p-3 text-xs font-mono">{c.conta_contabil ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
