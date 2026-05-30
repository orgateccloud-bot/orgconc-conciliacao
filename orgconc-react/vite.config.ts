import { readFileSync } from "node:fs";
import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const pkg = JSON.parse(readFileSync(path.resolve(__dirname, "./package.json"), "utf-8"));

export default defineConfig({
  plugins: [react()],
  base: "/app/",
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "/v1":          "http://127.0.0.1:8765",   // todas as rotas de negocio
      "/health":      "http://127.0.0.1:8765",
      "/auth":        "http://127.0.0.1:8765",
      "/logo-base64": "http://127.0.0.1:8765",
      "/ui":          "http://127.0.0.1:8765",
      // Compat: rotas legadas (sem /v1) seguem proxy enquanto coexistem
      "/conciliar":   "http://127.0.0.1:8765",
      "/export":      "http://127.0.0.1:8765",
      "/clientes":    "http://127.0.0.1:8765",
      "/serpro":      "http://127.0.0.1:8765",
      "/conciliacoes":"http://127.0.0.1:8765",
    },
  },
});
