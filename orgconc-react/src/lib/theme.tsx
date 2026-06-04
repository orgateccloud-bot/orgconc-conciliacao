import { createContext, useContext, useEffect, useState } from "react";

type Tema = "light" | "dark";
const STORAGE_KEY = "orgconc.tema.v1";

interface ThemeCtx {
  tema: Tema;
  toggle: () => void;
}

const Ctx = createContext<ThemeCtx>({ tema: "light", toggle: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [tema, setTema] = useState<Tema>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "light" || stored === "dark") return stored;
    } catch { /* ignore */ }
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", tema === "dark");
    root.setAttribute("data-theme", tema);
    try { localStorage.setItem(STORAGE_KEY, tema); } catch { /* ignore */ }
  }, [tema]);

  return (
    <Ctx.Provider value={{ tema, toggle: () => setTema(t => t === "light" ? "dark" : "light") }}>
      {children}
    </Ctx.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  return useContext(Ctx);
}
