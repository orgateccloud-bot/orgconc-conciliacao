import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import {
  listarOrgs,
  criarOrg,
  listarUsuarios,
  criarUsuario,
  resetarSenhaUsuario,
  type OrgAdmin,
  type UsuarioAdmin,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Users, Building2, KeyRound, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

const ROLE_CX: Record<string, string> = {
  admin:   "border-amber-200 bg-amber-100 text-amber-700",
  user:    "border-blue-200 bg-blue-100 text-blue-700",
  service: "border-violet-200 bg-violet-100 text-violet-700",
};
const ROLE_LABELS: Record<string, string> = {
  admin: "Admin", user: "Usuário", service: "Serviço",
};

export function UsuariosPage() {
  const { user } = useAuth();

  const [orgs, setOrgs] = useState<OrgAdmin[]>([]);
  const [orgId, setOrgId] = useState<string>("");
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [loadingOrgs, setLoadingOrgs] = useState(true);
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Nova organização
  const [orgNome, setOrgNome] = useState("");
  const [orgCnpj, setOrgCnpj] = useState("");
  const [orgPlano, setOrgPlano] = useState("basico");
  const [busyOrg, setBusyOrg] = useState(false);

  // Novo usuário
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [role, setRole] = useState("user");
  const [busyUser, setBusyUser] = useState(false);

  // Reset de senha
  const [reset, setReset] = useState<UsuarioAdmin | null>(null);
  const [senhaNova, setSenhaNova] = useState("");
  const [busyReset, setBusyReset] = useState(false);

  const orgSelecionada = useMemo(
    () => orgs.find((o) => o.id === orgId) || null,
    [orgs, orgId],
  );

  async function carregarOrgs(selecionar?: string) {
    setLoadingOrgs(true);
    try {
      const lista = await listarOrgs();
      setOrgs(lista);
      const alvo = selecionar || orgId || lista[0]?.id || "";
      setOrgId(alvo);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao listar organizações");
    } finally {
      setLoadingOrgs(false);
    }
  }

  async function carregarUsuarios(id: string) {
    if (!id) { setUsuarios([]); return; }
    setLoadingUsers(true);
    try {
      setUsuarios(await listarUsuarios(id));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao listar usuários");
    } finally {
      setLoadingUsers(false);
    }
  }

  useEffect(() => { carregarOrgs(); }, []);
  useEffect(() => { carregarUsuarios(orgId); }, [orgId]);

  // Gating: só admin acessa esta página.
  if (user && user.role !== "admin") {
    return <Navigate to="/dashboard" replace />;
  }

  async function salvarOrg(e: React.FormEvent) {
    e.preventDefault();
    setBusyOrg(true);
    try {
      const nova = await criarOrg({
        nome: orgNome.trim(),
        cnpj: orgCnpj.trim() || undefined,
        plano: orgPlano,
      });
      toast.success("Organização criada");
      setOrgNome(""); setOrgCnpj(""); setOrgPlano("basico");
      await carregarOrgs(nova.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao criar organização");
    } finally {
      setBusyOrg(false);
    }
  }

  async function salvarUsuario(e: React.FormEvent) {
    e.preventDefault();
    if (!orgId) { toast.error("Selecione uma organização"); return; }
    if (senha.length < 8) { toast.error("A senha precisa ter ao menos 8 caracteres"); return; }
    setBusyUser(true);
    try {
      await criarUsuario({
        email: email.trim(),
        senha,
        org_id: orgId,
        role,
        nome: nome.trim() || undefined,
      });
      toast.success("Usuário cadastrado");
      setEmail(""); setNome(""); setSenha(""); setRole("user");
      await carregarUsuarios(orgId);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao cadastrar usuário");
    } finally {
      setBusyUser(false);
    }
  }

  async function confirmarReset(e: React.FormEvent) {
    e.preventDefault();
    if (!reset) return;
    if (senhaNova.length < 8) { toast.error("A senha precisa ter ao menos 8 caracteres"); return; }
    setBusyReset(true);
    try {
      await resetarSenhaUsuario(reset.id, senhaNova);
      toast.success(`Senha de ${reset.email} redefinida — sessões revogadas`);
      setReset(null); setSenhaNova("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao redefinir senha");
    } finally {
      setBusyReset(false);
    }
  }

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="ADMIN · ACESSOS"
        title="Usuários &"
        titleAccent="organizações."
        subtitle="Cadastre o admin e os demais usuários, por organização."
      />

      {/* Nova organização */}
      <form onSubmit={salvarOrg} className="rounded-3xl border glass p-6 space-y-4">
        <h3 className="font-semibold text-base flex items-center gap-2">
          <Building2 className="h-4 w-4 text-primary" /> Nova organização
        </h3>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2 md:col-span-1">
            <Label>Nome *</Label>
            <Input value={orgNome} onChange={(e) => setOrgNome(e.target.value)} required placeholder="Razão social" />
          </div>
          <div className="space-y-2">
            <Label>CNPJ</Label>
            <Input value={orgCnpj} onChange={(e) => setOrgCnpj(e.target.value)} placeholder="00.000.000/0001-00" />
          </div>
          <div className="space-y-2">
            <Label>Plano</Label>
            <Select value={orgPlano} onValueChange={setOrgPlano}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="basico">Básico</SelectItem>
                <SelectItem value="pro">Pro</SelectItem>
                <SelectItem value="enterprise">Enterprise</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <Button type="submit" disabled={busyOrg || !orgNome.trim()}>
          {busyOrg ? "Criando…" : "Criar organização"}
        </Button>
      </form>

      {/* Seletor de organização */}
      <div className="rounded-3xl border glass p-6 space-y-2">
        <Label>Organização</Label>
        {loadingOrgs ? (
          <p className="text-sm text-muted-foreground">Carregando organizações…</p>
        ) : orgs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma organização ainda. Crie uma acima para cadastrar usuários.
          </p>
        ) : (
          <Select value={orgId} onValueChange={setOrgId}>
            <SelectTrigger className="md:w-96"><SelectValue placeholder="Selecione a organização" /></SelectTrigger>
            <SelectContent>
              {orgs.map((o) => (
                <SelectItem key={o.id} value={o.id}>
                  {o.nome}{o.cnpj ? ` · ${o.cnpj}` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Novo usuário */}
      <form onSubmit={salvarUsuario} className="rounded-3xl border glass p-6 space-y-4">
        <h3 className="font-semibold text-base flex items-center gap-2">
          <Plus className="h-4 w-4 text-primary" /> Cadastrar usuário
          {orgSelecionada && (
            <span className="text-xs font-normal text-muted-foreground">em {orgSelecionada.nome}</span>
          )}
        </h3>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>E-mail *</Label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="usuario@empresa.com" />
          </div>
          <div className="space-y-2">
            <Label>Nome</Label>
            <Input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Nome completo" />
          </div>
          <div className="space-y-2">
            <Label>Senha * <span className="text-muted-foreground font-normal">(mín. 8)</span></Label>
            <Input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required minLength={8} placeholder="••••••••" />
          </div>
          <div className="space-y-2">
            <Label>Papel</Label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="admin">Admin — gerencia a organização</SelectItem>
                <SelectItem value="user">Usuário — uso normal</SelectItem>
                <SelectItem value="service">Serviço — integração/automação</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <Button type="submit" disabled={busyUser || !orgId || !email.trim() || senha.length < 8}>
          {busyUser ? "Cadastrando…" : "Cadastrar usuário"}
        </Button>
      </form>

      {/* Tabela de usuários */}
      <div className="rounded-3xl border overflow-hidden">
        <div className="flex items-center gap-2 p-4 border-b bg-muted/30">
          <Users className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="text-sm font-semibold">Usuários{orgSelecionada ? ` · ${orgSelecionada.nome}` : ""}</span>
          <span className="ml-auto text-xs text-muted-foreground">{usuarios.length} usuário(s)</span>
        </div>

        {loadingUsers ? (
          <div className="p-6"><ListSkeleton items={3} /></div>
        ) : !orgId ? (
          <div className="p-12 flex flex-col items-center gap-3 text-center">
            <Building2 className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">Selecione uma organização para ver os usuários.</p>
          </div>
        ) : usuarios.length === 0 ? (
          <div className="p-12 flex flex-col items-center gap-3 text-center">
            <Users className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">Nenhum usuário nesta organização ainda.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3 font-semibold">E-mail</th>
                <th className="text-left p-3 font-semibold">Nome</th>
                <th className="text-left p-3 font-semibold">Papel</th>
                <th className="text-left p-3 font-semibold">Status</th>
                <th className="text-left p-3 font-semibold">Criado</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id} className="border-t hover:bg-muted/20">
                  <td className="p-3 font-medium">{u.email}</td>
                  <td className="p-3 text-muted-foreground">{u.nome || "—"}</td>
                  <td className="p-3">
                    <span className={cn(
                      "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold",
                      ROLE_CX[u.role] ?? "bg-gray-100 text-gray-700 border-gray-200",
                    )}>
                      {ROLE_LABELS[u.role] ?? u.role}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
                      u.ativo ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500",
                    )}>
                      {u.ativo ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-xs text-muted-foreground">
                    {u.criado_em ? u.criado_em.slice(0, 10) : "—"}
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => { setReset(u); setSenhaNova(""); }}
                      className="rounded p-1.5 hover:bg-secondary text-muted-foreground"
                      title="Redefinir senha"
                    >
                      <KeyRound className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Dialog: reset de senha */}
      <Dialog open={!!reset} onOpenChange={(o) => !o && setReset(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Redefinir senha</DialogTitle>
          </DialogHeader>
          <form onSubmit={confirmarReset} className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Nova senha para <span className="font-medium text-foreground">{reset?.email}</span>.
              As sessões ativas dele serão revogadas.
            </p>
            <div className="space-y-2">
              <Label>Nova senha <span className="text-muted-foreground font-normal">(mín. 8)</span></Label>
              <Input type="password" value={senhaNova} onChange={(e) => setSenhaNova(e.target.value)} required minLength={8} placeholder="••••••••" autoFocus />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setReset(null)}>Cancelar</Button>
              <Button type="submit" disabled={busyReset || senhaNova.length < 8}>
                {busyReset ? "Redefinindo…" : "Redefinir senha"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
