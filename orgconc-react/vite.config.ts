import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Proxy de API compartilhado entre `vite dev` (5176) e `vite preview` (4173).
// O preview precisa do proxy para os E2E exercitarem o backend REAL (uvicorn
// :8765) via chamadas relativas do app — sem ele, /conciliar etc. morrem no
// próprio preview. Cobre TODOS os prefixos do lib/api.ts (incl. /fiscal,
// /matchers, /guias, /contratos, que faltavam até no dev).
const API_PROXY: Record<string, string> = Object.fromEntries(
  [
    "/v1", "/health", "/conciliar", "/export", "/clientes", "/auth",
    "/conciliacoes", "/metrics", "/transacoes", "/audit", "/activity",
    "/ai", "/fiscal", "/matchers", "/guias", "/contratos", "/logo-base64",
  ].map((p) => [p, "http://127.0.0.1:8765"]),
);

export default defineConfig({
  plugins: [react()],
  base: "/app/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/recharts') || id.includes('node_modules/d3-')) return 'vendor-charts'
          if (id.includes('node_modules/@radix-ui')) return 'vendor-radix'
          if (id.includes('node_modules/react-dom') || id.includes('node_modules/react-router')) return 'vendor-react'
          if (id.includes('node_modules/@tanstack')) return 'vendor-query'
        }
      }
    }
  },
  server: {
    port: 5176,
    host: "127.0.0.1",
    proxy: API_PROXY,
  },
  preview: {
    port: 4173,
    proxy: API_PROXY,
  },
});
