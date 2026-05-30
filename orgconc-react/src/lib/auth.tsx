import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  apiLogout,
  apiRefresh,
  fetchMe,
  getToken,
  jwtExpMs,
  login as apiLogin,
  setToken,
  type UserMe,
} from "@/lib/api";

interface AuthState {
  user: UserMe | null;
  loading: boolean;
  login: (email: string, senha: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

// Renova quando faltar este tempo (ms) para expirar.
const REFRESH_LEAD_MS = 60_000;  // 1 min antes
// Backoff entre tentativas se o exp ja passou.
const RETRY_MS = 30_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [loading, setLoading] = useState(true);
  const refreshTimer = useRef<number | null>(null);

  const cancelTimer = useCallback(() => {
    if (refreshTimer.current !== null) {
      window.clearTimeout(refreshTimer.current);
      refreshTimer.current = null;
    }
  }, []);

  const scheduleRefresh = useCallback(() => {
    cancelTimer();
    const token = getToken();
    const exp = jwtExpMs(token);
    if (!exp) return;
    const delay = Math.max(exp - Date.now() - REFRESH_LEAD_MS, 0);
    refreshTimer.current = window.setTimeout(async () => {
      const novo = await apiRefresh();
      if (novo) {
        scheduleRefresh();
      } else {
        // Backoff: tenta de novo em 30s, caso conexao tenha falhado
        refreshTimer.current = window.setTimeout(scheduleRefresh, RETRY_MS);
      }
    }, delay);
  }, [cancelTimer]);

  const refresh = useCallback(async () => {
    try {
      const me = await fetchMe();
      setUser(me);
      scheduleRefresh();
    } catch {
      if (!getToken()) setUser(null);
      else {
        setUser(null);
        setToken(null);
      }
      cancelTimer();
    } finally {
      setLoading(false);
    }
  }, [scheduleRefresh, cancelTimer]);

  useEffect(() => {
    refresh();
    const onLogout = () => {
      setUser(null);
      setToken(null);
      cancelTimer();
    };
    window.addEventListener("orgconc:logout", onLogout);
    return () => {
      window.removeEventListener("orgconc:logout", onLogout);
      cancelTimer();
    };
  }, [refresh, cancelTimer]);

  const login = useCallback(async (email: string, senha: string) => {
    const res = await apiLogin(email, senha);
    setToken(res.access_token);
    await refresh();
  }, [refresh]);

  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
    cancelTimer();
  }, [cancelTimer]);

  const value = useMemo(
    () => ({ user, loading, login, logout }),
    [user, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fora de AuthProvider");
  return ctx;
}
