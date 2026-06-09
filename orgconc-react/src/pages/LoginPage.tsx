import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { ComplianceBadges } from "@/components/dashboard/ComplianceBadges";
import { Button } from "@/components/ui/button";
import { ArrowRight, Eye, EyeOff, ScrollText, ShieldCheck, Sparkles } from "lucide-react";
import { toast } from "sonner";

const LAST_LOGIN_KEY = "orgatec_last_login";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [lastLogin, setLastLogin] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(LAST_LOGIN_KEY);
    if (stored) {
      const d = new Date(stored);
      setLastLogin(
        d.toLocaleString("pt-BR", {
          day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
        }),
      );
    }
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (senha.length < 8) {
      toast.error("Senha deve ter pelo menos 8 caracteres");
      return;
    }
    setBusy(true);
    try {
      await login(email, senha);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha no login");
      setBusy(false);
      return;
    }
    try {
      localStorage.setItem(LAST_LOGIN_KEY, new Date().toISOString());
    } catch {
      /* modo privado / storage cheio — ignorar */
    }
    toast.success("Sessão iniciada");
    setBusy(false);
    navigate("/dashboard");
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2" style={{ background: "var(--d-bg)" }}>
      {/* Painel da marca (desktop) */}
      <div className="relative hidden lg:flex flex-col justify-between overflow-hidden bg-brand-gradient p-12 text-white">
        <div className="absolute -top-32 -right-32 h-80 w-80 rounded-full bg-white/10 blur-3xl" aria-hidden="true" />
        <div className="relative flex items-center gap-3">
          <Logo size={44} />
          <div>
            <p className="text-xl font-bold leading-none tracking-tight">ORGATEC</p>
            <p className="mt-1 text-[11px] font-mono uppercase tracking-[0.18em] text-white/70">
              Conciliação Bancária
            </p>
          </div>
        </div>

        <div className="relative max-w-md">
          <h2 className="mb-4 text-3xl font-bold leading-tight">
            Onde a conciliação encontra a auditoria.
          </h2>
          <p className="mb-8 leading-relaxed text-white/80">
            Importe extratos, concilie automaticamente e gere a trilha de auditoria —
            com isolamento por organização e criptografia ponta a ponta.
          </p>
          <ul className="space-y-3 text-sm text-white/90">
            <li className="flex items-center gap-2.5">
              <Sparkles className="h-4 w-4 shrink-0" aria-hidden="true" /> Conciliação automática com matchers
            </li>
            <li className="flex items-center gap-2.5">
              <ScrollText className="h-4 w-4 shrink-0" aria-hidden="true" /> Laudo forense e fiscal integrado
            </li>
            <li className="flex items-center gap-2.5">
              <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden="true" /> Trilha imutável (hash chain) por organização
            </li>
          </ul>
        </div>

        <p className="relative text-[11px] text-white/60">ORGATEC · Contabilidade &amp; Auditoria</p>
      </div>

      {/* Formulário */}
      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm">
          {/* Marca (mobile) */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <Logo size={36} />
            <div>
              <p className="font-bold leading-none">ORGATEC</p>
              <p className="mt-0.5 text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                Conciliação Bancária
              </p>
            </div>
          </div>

          <h1 className="text-2xl font-bold tracking-tight">Entrar</h1>
          <p className="mb-6 mt-1 text-sm text-muted-foreground">
            Acesse o painel com suas credenciais.
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="lp-email" className="text-xs font-medium text-muted-foreground">
                E-mail
              </label>
              <input
                id="lp-email"
                type="email"
                autoComplete="email"
                maxLength={254}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="voce@empresa.com"
                className="flex h-10 w-full rounded-lg border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="lp-senha" className="text-xs font-medium text-muted-foreground">
                Senha
              </label>
              <div className="relative">
                <input
                  id="lp-senha"
                  type={showPw ? "text" : "password"}
                  autoComplete="current-password"
                  maxLength={128}
                  required
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  placeholder="••••••••"
                  className="flex h-10 w-full rounded-lg border border-input bg-background px-3 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  aria-label={showPw ? "Ocultar senha" : "Mostrar senha"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground"
                >
                  {showPw ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                </button>
              </div>
            </div>

            <Button type="submit" disabled={busy} className="w-full gap-2">
              {busy ? "Verificando…" : "Acessar painel"}
              {!busy && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
            </Button>
          </form>

          <div className="mt-6">
            <ComplianceBadges />
          </div>

          {lastLogin && (
            <p className="mt-4 text-[11px] text-muted-foreground">
              Último acesso: <span className="font-mono">{lastLogin}</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
