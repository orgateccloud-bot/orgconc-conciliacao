import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

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
    proxy: {
      "/v1":          "http://127.0.0.1:8765",
      "/health":      "http://127.0.0.1:8765",
      "/conciliar":   "http://127.0.0.1:8765",
      "/export":      "http://127.0.0.1:8765",
      "/clientes":    "http://127.0.0.1:8765",
      "/auth":        "http://127.0.0.1:8765",
      "/conciliacoes":"http://127.0.0.1:8765",
      "/metrics":     "http://127.0.0.1:8765",
      "/transacoes":  "http://127.0.0.1:8765",
      "/audit":       "http://127.0.0.1:8765",
      "/activity":    "http://127.0.0.1:8765",
      "/ai":          "http://127.0.0.1:8765",
      "/logo-base64": "http://127.0.0.1:8765",
    },
  },
});
