import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { HeroCard } from "@/components/HeroCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Moon, Sun, User, Server, Palette } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchHealth, type HealthResponse } from "@/lib/api";

export function ConfiguracoesPage() {
  const { user } = useAuth();
  const { tema, toggle } = useTheme();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmSenha, setConfirmSenha] = useState("");

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => {});
  }, []);

  const senhasOk = novaSenha.length >= 8 && novaSenha === confirmSenha;

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="04 · CONFIGURAÇÕES"
        title="Preferências e"
        titleAccent="sistema."
        subtitle="Gerenciar conta, aparência e verificar status do servidor."
      />

      {/* Conta */}
      <section className="rounded-3xl border glass p-6 space-y-5">
        <div className="flex items-center gap-2 pb-1">
          <User className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold">Conta</h3>
        </div>
        <div className="grid gap-4 md:grid-cols-2 text-sm">
          <div>
            <p className="text-[11px] font-mono uppercase text-muted-foreground mb-1">
              E-mail / usuário
            </p>
            <p className="font-medium">{user?.email || user?.sub || "—"}</p>
          </div>
          <div>
            <p className="text-[11px] font-mono uppercase text-muted-foreground mb-1">Papel</p>
            <p className="font-medium capitalize">{user?.role || "—"}</p>
          </div>
        </div>

        <div className="border-t pt-4 space-y-4">
          <p className="text-[11px] font-mono uppercase text-muted-foreground tracking-wide">
            Alterar senha
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>
                Nova senha{" "}
                <span className="text-muted-foreground font-normal">(mín. 8 caracteres)</span>
              </Label>
              <Input
                type="password"
                value={novaSenha}
                onChange={(e) => setNovaSenha(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            <div className="space-y-2">
              <Label>Confirmar senha</Label>
              <Input
                type="password"
                value={confirmSenha}
                onChange={(e) => setConfirmSenha(e.target.value)}
                placeholder="••••••••"
              />
            </div>
          </div>
          {confirmSenha && !senhasOk && (
            <p className="text-xs text-destructive">
              As senhas não coincidem ou são muito curtas.
            </p>
          )}
          <Button
            disabled={!senhasOk}
            variant="outline"
            size="sm"
            title="Funcionalidade em desenvolvimento"
          >
            Atualizar senha <span className="text-muted-foreground ml-1">(em breve)</span>
          </Button>
        </div>
      </section>

      {/* Interface */}
      <section className="rounded-3xl border glass p-6 space-y-5">
        <div className="flex items-center gap-2 pb-1">
          <Palette className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold">Interface</h3>
        </div>

        <div className="flex items-center justify-between rounded-2xl border bg-muted/30 px-4 py-3">
          <div>
            <p className="text-sm font-medium">Tema</p>
            <p className="text-xs text-muted-foreground">
              Atualmente:{" "}
              <span className="font-semibold">{tema === "dark" ? "Escuro" : "Claro"}</span>
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={toggle} className="gap-2">
            {tema === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
            {tema === "dark" ? "Mudar para claro" : "Mudar para escuro"}
          </Button>
        </div>

        <div className="flex items-center gap-3 rounded-2xl border bg-muted/30 px-4 py-3">
          <div className="h-8 w-8 rounded-xl bg-brand-gradient shrink-0" />
          <div>
            <p className="text-sm font-medium">Design System: Direção Leve</p>
            <p className="text-xs text-muted-foreground">
              Manrope · Instrument Serif · JetBrains Mono · Paleta Navy / Azure
            </p>
          </div>
        </div>
      </section>

      {/* Status do servidor */}
      <section className="rounded-3xl border glass p-6 space-y-5">
        <div className="flex items-center gap-2 pb-1">
          <Server className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold">Status do servidor</h3>
        </div>

        {health ? (
          <div className="grid gap-3 md:grid-cols-2 text-sm">
            {[
              { label: "Status",      value: health.status,                                          ok: health.status === "ok" },
              { label: "Versão",      value: health.versao,                                          ok: true },
              { label: "Banco",       value: health.banco_dados,                                     ok: health.banco_dados === "ok" },
              { label: "API Claude",  value: health.api_key_configured ? "Configurada" : "Ausente",  ok: health.api_key_configured },
            ].map(({ label, value, ok }) => (
              <div
                key={label}
                className="flex items-center justify-between rounded-xl border bg-muted/30 px-4 py-3"
              >
                <span className="text-muted-foreground font-mono text-[11px] uppercase">
                  {label}
                </span>
                <span
                  className={cn(
                    "font-semibold text-xs",
                    ok ? "text-green-600" : "text-orange-500"
                  )}
                >
                  {value}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 rounded-xl bg-muted animate-pulse" />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
