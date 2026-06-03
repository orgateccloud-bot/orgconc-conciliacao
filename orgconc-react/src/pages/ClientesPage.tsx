import { useEffect, useMemo, useState } from "react";
import {
  criarCliente,
  atualizarCliente,
  listarClientes,
  listarConciliacoesDoCliente,
  invalidarCacheClientes,
  type Cliente,
  type ConciliacaoMeta,
} from "@/lib/api";
import { HeroCard } from "@/components/HeroCard";
import { ListSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Search, Pencil, Building2, Users, Download } from "lucide-react";
import { cn } from "@/lib/utils";

function validarCnpj(cnpj: string): boolean {
  const d = cnpj.replace(/\D/g, "");
  if (d.length !== 14 || new Set(d.split("")).size === 1) return false;
  const calc = (digits: string, pesos: number[]) => {
    const r = pesos.reduce((s, p, i) => s + parseInt(digits[i]) * p, 0) % 11;
    return r < 2 ? 0 : 11 - r;
  };
  return (
    calc(d, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]) === parseInt(d[12]) &&
    calc(d, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]) === parseInt(d[13])
  );
}

const PLANO_CX: Record<string, string> = {
  basico:     "border-gray-200 bg-gray-100 text-gray-700",
  pro:        "border-blue-200 bg-blue-100 text-blue-700",
  enterprise: "border-amber-200 bg-amber-100 text-amber-700",
};

const PLANO_LABELS: Record<string, string> = {
  basico:     "Básico",
  pro:        "Pro",
  enterprise: "Enterprise",
};

export function ClientesPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [busca, setBusca] = useState("");
  const [loading, setLoading] = useState(true);

  // Create form
  const [nome, setNome] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [email, setEmail] = useState("");
  const [telefone, setTelefone] = useState("");
  const [plano, setPlano] = useState("basico");

  // Edit dialog
  const [editando, setEditando] = useState<Cliente | null>(null);
  const [editNome, setEditNome] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editTelefone, setEditTelefone] = useState("");
  const [editPlano, setEditPlano] = useState("basico");
  const [editAtivo, setEditAtivo] = useState(true);
  const [busyEdit, setBusyEdit] = useState(false);

  // Detail sheet
  const [detalhe, setDetalhe] = useState<Cliente | null>(null);
  const [historico, setHistorico] = useState<ConciliacaoMeta[]>([]);
  const [loadingHistorico, setLoadingHistorico] = useState(false);

  async function carregar() {
    setLoading(true);
    try {
      setClientes(await listarClientes());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao listar clientes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { carregar(); }, []);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (cnpj.trim() && !validarCnpj(cnpj)) {
      toast.error("CNPJ inválido — verifique os dígitos verificadores");
      return;
    }
    try {
      await criarCliente({
        nome,
        cnpj: cnpj || undefined,
        email: email || undefined,
        telefone: telefone || undefined,
        plano,
      });
      invalidarCacheClientes();
      toast.success("Cliente cadastrado");
      setNome(""); setCnpj(""); setEmail(""); setTelefone(""); setPlano("basico");
      await carregar();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao cadastrar");
    }
  }

  function abrirEdicao(c: Cliente, e: React.MouseEvent) {
    e.stopPropagation();
    setEditando(c);
    setEditNome(c.nome);
    setEditEmail(c.email ?? "");
    setEditTelefone(c.telefone ?? "");
    setEditPlano(c.plano);
    setEditAtivo(c.ativo !== false);
  }

  async function salvarEdicao() {
    if (!editando) return;
    setBusyEdit(true);
    try {
      await atualizarCliente(editando.id, {
        nome: editNome,
        email: editEmail || undefined,
        telefone: editTelefone || undefined,
        plano: editPlano,
        ativo: editAtivo,
      });
      toast.success("Cliente atualizado");
      setEditando(null);
      await carregar();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao atualizar");
    } finally {
      setBusyEdit(false);
    }
  }

  async function abrirDetalhe(c: Cliente) {
    setDetalhe(c);
    setHistorico([]);
    setLoadingHistorico(true);
    try {
      const h = await listarConciliacoesDoCliente(c.id);
      setHistorico(h);
    } catch {
      // DB pode não estar configurado
    } finally {
      setLoadingHistorico(false);
    }
  }

  const clientesFiltrados = useMemo(() => {
    const q = busca.toLowerCase();
    if (!q) return clientes;
    return clientes.filter(
      (c) => c.nome.toLowerCase().includes(q) || (c.cnpj ?? "").includes(q)
    );
  }, [clientes, busca]);

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="02 · CLIENTES"
        title="Cadastro"
        titleAccent="fiscal."
        subtitle="Carteira de empresas com validação de CNPJ."
      />

      {/* Create form */}
      <form onSubmit={salvar} className="rounded-3xl border glass p-6 space-y-4">
        <h3 className="font-semibold text-base">Novo cliente</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2 md:col-span-2">
            <Label>Nome *</Label>
            <Input
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              required
              placeholder="Razão social ou nome"
            />
          </div>
          <div className="space-y-2">
            <Label>CNPJ</Label>
            <Input
              value={cnpj}
              onChange={(e) => setCnpj(e.target.value)}
              placeholder="00.000.000/0001-00"
            />
          </div>
          <div className="space-y-2">
            <Label>Plano</Label>
            <Select value={plano} onValueChange={setPlano}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="basico">Básico</SelectItem>
                <SelectItem value="pro">Pro</SelectItem>
                <SelectItem value="enterprise">Enterprise</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>E-mail</Label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Telefone</Label>
            <Input value={telefone} onChange={(e) => setTelefone(e.target.value)} placeholder="(11) 99999-9999" />
          </div>
        </div>

        <Button type="submit" disabled={!nome.trim()}>Cadastrar cliente</Button>
      </form>

      {/* Table */}
      <div className="rounded-3xl border overflow-hidden">
        <div className="flex items-center gap-2 p-4 border-b bg-muted/30">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <Input
            placeholder="Buscar por nome ou CNPJ…"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            className="h-8 border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 p-0"
          />
          <span className="text-xs text-muted-foreground shrink-0">
            {clientesFiltrados.length} resultado(s)
          </span>
        </div>

        {loading ? (
          <div className="p-6">
            <ListSkeleton items={3} />
          </div>
        ) : clientesFiltrados.length === 0 ? (
          <div className="p-12 flex flex-col items-center gap-3 text-center">
            <Users className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              {busca
                ? "Nenhum cliente encontrado para esta busca."
                : "Nenhum cliente cadastrado ainda."}
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3 font-semibold">Nome</th>
                <th className="text-left p-3 font-semibold">CNPJ</th>
                <th className="text-left p-3 font-semibold">Plano</th>
                <th className="text-left p-3 font-semibold">Status</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {clientesFiltrados.map((c) => (
                <tr
                  key={c.id}
                  className="border-t hover:bg-muted/20 cursor-pointer"
                  onClick={() => abrirDetalhe(c)}
                >
                  <td className="p-3 font-medium">{c.nome}</td>
                  <td className="p-3 font-mono text-xs">{c.cnpj || "—"}</td>
                  <td className="p-3">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold",
                        PLANO_CX[c.plano] ?? "bg-gray-100 text-gray-700 border-gray-200"
                      )}
                    >
                      {PLANO_LABELS[c.plano] ?? c.plano}
                    </span>
                  </td>
                  <td className="p-3">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
                        c.ativo !== false
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      )}
                    >
                      {c.ativo !== false ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={(e) => abrirEdicao(c, e)}
                      className="rounded p-1.5 hover:bg-secondary text-muted-foreground"
                      title="Editar cliente"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Edit dialog */}
      <Dialog open={!!editando} onOpenChange={(o) => !o && setEditando(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar cliente</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Nome *</Label>
              <Input
                value={editNome}
                onChange={(e) => setEditNome(e.target.value)}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>E-mail</Label>
                <Input
                  type="email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Telefone</Label>
                <Input
                  value={editTelefone}
                  onChange={(e) => setEditTelefone(e.target.value)}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Plano</Label>
                <Select value={editPlano} onValueChange={setEditPlano}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="basico">Básico</SelectItem>
                    <SelectItem value="pro">Pro</SelectItem>
                    <SelectItem value="enterprise">Enterprise</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={editAtivo ? "ativo" : "inativo"}
                  onValueChange={(v) => setEditAtivo(v === "ativo")}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ativo">Ativo</SelectItem>
                    <SelectItem value="inativo">Inativo</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditando(null)}>Cancelar</Button>
            <Button
              onClick={salvarEdicao}
              disabled={busyEdit || !editNome.trim()}
            >
              {busyEdit ? "Salvando…" : "Salvar alterações"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detail sheet */}
      <Sheet open={!!detalhe} onOpenChange={(o) => !o && setDetalhe(null)}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto" side="right">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              {detalhe?.nome}
            </SheetTitle>
          </SheetHeader>
          {detalhe && (
            <div className="mt-6 space-y-6">
              <div className="space-y-2 text-sm">
                {detalhe.cnpj && (
                  <div>
                    <span className="text-muted-foreground">CNPJ: </span>
                    <span className="font-mono">{detalhe.cnpj}</span>
                  </div>
                )}
                {detalhe.email && (
                  <div>
                    <span className="text-muted-foreground">E-mail: </span>
                    {detalhe.email}
                  </div>
                )}
                {detalhe.telefone && (
                  <div>
                    <span className="text-muted-foreground">Telefone: </span>
                    {detalhe.telefone}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">Plano:</span>
                  <span className={cn(
                    "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold",
                    PLANO_CX[detalhe.plano] ?? ""
                  )}>
                    {PLANO_LABELS[detalhe.plano] ?? detalhe.plano}
                  </span>
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-sm mb-3">Histórico de conciliações</h4>
                {loadingHistorico ? (
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-16 rounded-md bg-muted animate-pulse" />
                    ))}
                  </div>
                ) : historico.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Nenhuma conciliação vinculada a este cliente.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {historico.map((r) => (
                      <div
                        key={r.report_id}
                        className="rounded-xl border p-3 text-sm flex items-start gap-3"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="font-mono text-xs text-muted-foreground truncate">
                            {r.report_id.slice(0, 12)}…
                          </div>
                          <div className="flex flex-wrap gap-2 mt-1 text-xs">
                            <span className="font-medium">{r.modo}</span>
                            <span className="text-muted-foreground">·</span>
                            <span>{r.total_transacoes} tx</span>
                            <span className="text-muted-foreground">·</span>
                            <span className={r.total_anomalias > 0 ? "text-orange-500 font-semibold" : "text-green-600"}>
                              {r.total_anomalias} anom.
                            </span>
                          </div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {new Date(r.criado_em).toLocaleDateString("pt-BR")}
                          </div>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          {[
                            { href: r.exports.html, title: "HTML" },
                            { href: r.exports.xlsx, title: "Excel" },
                            { href: r.exports.pdf, title: "PDF" },
                          ].map(({ href, title }) => (
                            <a
                              key={title}
                              href={href}
                              title={title}
                              className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                            >
                              <Download className="h-3.5 w-3.5" />
                            </a>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

