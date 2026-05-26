import { useEffect, useState } from "react";

/**
 * Relogio HH:MM com sufixo de timezone — atualiza a cada segundo.
 * Reusavel em Topbar, LoginPage, dashboards.
 */
export function useClock(suffix = "BRT"): string {
  const [time, setTime] = useState("");
  useEffect(() => {
    const fmt = () => {
      const now = new Date();
      const h = String(now.getHours()).padStart(2, "0");
      const m = String(now.getMinutes()).padStart(2, "0");
      setTime(`${h}:${m} ${suffix}`);
    };
    fmt();
    const id = setInterval(fmt, 1000);
    return () => clearInterval(id);
  }, [suffix]);
  return time;
}
