import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, apiLogout, fetchMe, getToken, limparDadosTenant, login as apiLogin, setToken, type UserMe } from "@/lib/api";

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
    } catch (err) {
      // Só destrói a sessão em rejeição real de auth (401/403). Falha de rede
      // transitória (TypeError: Failed to fetch) preserva o token — deslogar
      // por queda de wi-fi é punir o usuário pelo problema errado.
      const ehAuth = err instanceof ApiError && (err.status === 401 || err.status === 403);
      setUser(null);
      if (ehAuth && getToken()) setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const onLogout = () => {
      setUser(null);
      setToken(null);
      limparDadosTenant();
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
