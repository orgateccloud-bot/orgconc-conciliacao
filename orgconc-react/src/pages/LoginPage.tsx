import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { APP_VERSION } from "@/lib/version";
import { toast } from "sonner";
import s from "./LoginPage.module.css";

// ── Hooks ─────────────────────────────────────────────────────────────────

function useClock() {
  const [time, setTime] = useState("");
  useEffect(() => {
    const fmt = () => {
      const now = new Date();
      const h = String(now.getHours()).padStart(2, "0");
      const m = String(now.getMinutes()).padStart(2, "0");
      setTime(`${h}:${m} BRT`);
    };
    fmt();
    const id = setInterval(fmt, 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

function useStarfield(canvasRef: React.RefObject<HTMLCanvasElement>) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    type Star = { x: number; y: number; r: number; a: number; da: number };
    let stars: Star[] = [];
    let rafId: number;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    const init = () => {
      stars = Array.from({ length: 180 }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.2 + 0.3,
        a: Math.random(),
        da: (Math.random() - 0.5) * 0.004,
      }));
    };
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const s of stars) {
        s.a = Math.max(0.05, Math.min(1, s.a + s.da));
        if (s.a <= 0.05 || s.a >= 1) s.da *= -1;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(200,220,255,${s.a})`;
        ctx.fill();
      }
      rafId = requestAnimationFrame(draw);
    };

    const onResize = () => { resize(); init(); };

    resize();
    init();
    draw();
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
    };
  }, [canvasRef]);
}

// ── Component ─────────────────────────────────────────────────────────────

const LAST_LOGIN_KEY = "orgatec_last_login";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [lastLogin, setLastLogin] = useState("primeira vez");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const clock = useClock();

  useStarfield(canvasRef);

  useEffect(() => {
    const stored = localStorage.getItem(LAST_LOGIN_KEY);
    if (stored) {
      const d = new Date(stored);
      setLastLogin(
        d.toLocaleString("pt-BR", {
          day: "2-digit", month: "short",
          hour: "2-digit", minute: "2-digit",
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
      localStorage.setItem(LAST_LOGIN_KEY, new Date().toISOString());
      toast.success("Sessão iniciada");
      navigate("/conciliacao");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha no login");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={s.root}>
      <canvas ref={canvasRef} className={s.starCanvas} />

      <div className={`${s.auroraBand} ${s.a1}`} />
      <div className={`${s.auroraBand} ${s.a2}`} />
      <div className={`${s.auroraBand} ${s.a3}`} />
      <div className={`${s.auroraBand} ${s.a4}`} />
      <div className={s.auroraLine} />
      <div className={s.shoot} />

      {/* Rail */}
      <header className={s.rail}>
        <div className={s.lhs}>
          <span className={s.mark}></span>
          <span>ORGATEC / V{APP_VERSION}</span>
        </div>
        <div className={s.rhs}>
          <span className={s.clock}>{clock}</span>
          <span className={s.model}>CLAUDE <strong>SONNET</strong></span>
          <span>BR-GRU-1 ·</span>
          <span className={s.online}>ONLINE</span>
        </div>
      </header>

      {/* Cert banner */}
      <div className={s.certBanner}>
        <span><span className={s.dotSm} /> PLATAFORMA CERTIFICADA</span>
        <span>·</span>
        <span>SESSÃO SEGURA</span>
      </div>

      <div className={s.page}>

        {/* Left — editorial */}
        <div className={s.colLeft}>
          <div className={s.brandMark}>
            <svg className={s.logoIcon} viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
              <ellipse cx="40" cy="40" rx="28" ry="28" stroke="url(#lp-lg1)" strokeWidth="3" />
              <ellipse cx="40" cy="40" rx="16" ry="28" stroke="url(#lp-lg2)" strokeWidth="2" opacity=".7" />
              <ellipse cx="40" cy="40" rx="28" ry="10" stroke="url(#lp-lg3)" strokeWidth="2" opacity=".5" />
              <circle cx="40" cy="12" r="3" fill="#38BDF8" opacity=".9" />
              <defs>
                <linearGradient id="lp-lg1" x1="12" y1="12" x2="68" y2="68">
                  <stop offset="0%" stopColor="#38BDF8" />
                  <stop offset="100%" stopColor="#0052FF" />
                </linearGradient>
                <linearGradient id="lp-lg2" x1="40" y1="12" x2="40" y2="68">
                  <stop offset="0%" stopColor="#0EA5E9" />
                  <stop offset="100%" stopColor="#38BDF8" stopOpacity=".4" />
                </linearGradient>
                <linearGradient id="lp-lg3" x1="12" y1="40" x2="68" y2="40">
                  <stop offset="0%" stopColor="#0052FF" stopOpacity=".3" />
                  <stop offset="100%" stopColor="#38BDF8" />
                </linearGradient>
              </defs>
            </svg>
            <div className={s.wordmark}>
              <span className={s.wordmarkTop}>ORG<span className={s.dot} /></span>
              <span className={s.wordmarkBot}>atec.</span>
            </div>
          </div>

          <p className={s.tagline}>
            Conciliação bancária inteligente — onde a IA encontra a
            auditoria, com precisão de 99,8% e trilha criptográfica.
          </p>

          <div className={s.statsRow}>
            <div className={s.stat}>
              <span className={s.statLabel}>Transações</span>
              <span className={s.statValue}><em>12.5M</em> R$/mês</span>
            </div>
            <div className={s.stat}>
              <span className={s.statLabel}>Motor IA</span>
              <span className={s.statValue}>Claude <span className={s.aiName}>Sonnet</span></span>
            </div>
            <div className={s.stat}>
              <span className={s.statLabel}>Última Sessão</span>
              <span className={s.statValue}>{lastLogin}</span>
            </div>
          </div>
        </div>

        {/* Right — form */}
        <div className={s.colRight}>
          <div className={s.loginCard}>
            <div className={s.loginHeading}>
              <h1>Entrar.</h1>
              <div className={s.sub}>O ledger aguarda.</div>
              <p>Use suas credenciais corporativas para acessar o painel.</p>
            </div>

            <form onSubmit={onSubmit}>
              <div className={s.field}>
                <label htmlFor="lp-email">E-mail corporativo</label>
                <input
                  id="lp-email"
                  type="email"
                  placeholder="seu.nome@empresa.com"
                  autoComplete="email"
                  maxLength={254}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className={`${s.field} ${s.fieldPw}`}>
                <label htmlFor="lp-senha">Senha</label>
                <input
                  id="lp-senha"
                  type={showPw ? "text" : "password"}
                  placeholder="••••••••••••"
                  autoComplete="current-password"
                  maxLength={128}
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className={s.eyeBtn}
                  onClick={() => setShowPw((v) => !v)}
                  aria-label={showPw ? "Ocultar senha" : "Mostrar senha"}
                >
                  {showPw ? (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>

              <button type="submit" className={s.cta} disabled={busy}>
                <span>{busy ? "VERIFICANDO…" : "ACESSAR PLATAFORMA"}</span>
                <span className={s.arrow}>{busy ? "…" : "→"}</span>
              </button>
            </form>

            <div className={s.orDivider}>OU</div>

            <div className={s.altAuth}>
              <button className={s.altBtn} disabled title="Em breve">SSO</button>
              <button className={s.altBtn} disabled title="Em breve">HARDWARE KEY</button>
            </div>
          </div>
        </div>

      </div>

      {/* Footer */}
      <footer className={s.strip}>
        <div className={s.certs}>
          <span>Acesso monitorado: <em>LGPD</em></span>
          <span>·</span>
          <span><em>SOC 2</em></span>
          <span>·</span>
          <span><em>ISO 27001</em></span>
        </div>
        <div>ORGATEC · CFC-GO · LC 224/2025</div>
      </footer>
    </div>
  );
}
