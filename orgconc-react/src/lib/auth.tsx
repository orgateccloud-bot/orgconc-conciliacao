import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiLogout, fetchMe, getToken, login as apiLogin, setToken, type UserMe } from "@/lib/api";

interface AuthState {
  user: UserMe | null;
  loading: boolean;
  login: (email: string, senha: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await fetchMe();
      setUser(me);
    } catch {
      // DEV (sem tela de login): mantém o app utilizável com um usuário sintético
      // mesmo se /auth/me falhar. Em prod, comportamento normal.
      if (import.meta.env.DEV) {
        setUser({ sub: "dev", email: "dev@orgconc.local", role: "admin" });
      } else if (!getToken()) {
        setUser(null);
      } else {
        setUser(null);
        setToken(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // DEV: auto-login com o service token (VITE_DEV_AUTH_TOKEN em .env.local) para
    // as chamadas autenticarem enquanto a tela de login é refeita. No-op em prod.
    if (import.meta.env.DEV) {
      const devTok = import.meta.env.VITE_DEV_AUTH_TOKEN as string | undefined;
      if (devTok && !getToken()) setToken(devTok);
    }
    refresh();
    const onLogout = () => {
      setUser(null);
      setToken(null);
    };
    window.addEventListener("orgconc:logout", onLogout);
    return () => window.removeEventListener("orgconc:logout", onLogout);
  }, [refresh]);

  const login = useCallback(async (email: string, senha: string) => {
    const res = await apiLogin(email, senha);
    setToken(res.access_token);
    await refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, logout }),
    [user, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fora de AuthProvider");
  return ctx;
}
