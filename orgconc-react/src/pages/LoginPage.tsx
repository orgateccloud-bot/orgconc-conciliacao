import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/Logo";
import { toast } from "sonner";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (senha.length < 8) {
      toast.error("Senha deve ter pelo menos 8 caracteres");
      return;
    }
    setBusy(true);
    try {
      await login(email, senha);
      toast.success("Sessão iniciada");
      navigate("/conciliacao");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha no login");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "var(--d-bg)" }}>
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-3xl border bg-card p-8 space-y-6 shadow-sm"
      >
        <div className="flex flex-col items-center gap-2">
          <Logo size={64} />
          <h1 className="text-xl font-bold">ORGATEC · OrgConc</h1>
          <p className="text-sm text-muted-foreground text-center">
            Entre com as credenciais do administrador configuradas no servidor.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">E-mail</Label>
          <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="senha">Senha</Label>
          <Input id="senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required />
        </div>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "Entrando…" : "Entrar"}
        </Button>
      </form>
    </div>
  );
}
