import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "/health":      "http://127.0.0.1:8765",
      "/conciliar":   "http://127.0.0.1:8765",
      "/export":      "http://127.0.0.1:8765",
      "/clientes":    "http://127.0.0.1:8765",
      "/auth":        "http://127.0.0.1:8765",
      "/serpro":      "http://127.0.0.1:8765",
      "/conciliacoes":"http://127.0.0.1:8765",
      "/logo-base64": "http://127.0.0.1:8765",
      "/ui":          "http://127.0.0.1:8765",
    },
  },
});
