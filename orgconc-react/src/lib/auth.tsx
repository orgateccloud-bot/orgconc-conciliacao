import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { fetchMe, getToken, login as apiLogin, setToken, type UserMe } from "@/lib/api";

interface AuthState {
  user: UserMe | null;
  loading: boolean;
  login: (email: string, senha: string) => Promise<void>;
  logout: () => void;
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
      if (!getToken()) setUser(null);
      else {
        setUser(null);
        setToken(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
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

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

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
