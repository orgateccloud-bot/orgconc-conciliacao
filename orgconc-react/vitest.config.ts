import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["tests/**", "node_modules/**", "dist/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      exclude: [
        "node_modules/**",
        "dist/**",
        "src/components/ui/**",
        "src/test/**",
        "**/*.config.*",
        "**/*.d.ts",
      ],
      // Gate (ratchet): piso ~2-3pts abaixo do atingido em 2026-06-09
      // (stmts 75.8 / branches 65.1 / funcs 72.5 / lines 78.1).
      // Trava o ganho sem fragilizar o CI; subir conforme a cobertura crescer.
      thresholds: {
        statements: 73,
        branches: 62,
        functions: 68,
        lines: 75,
      },
    },
  },
});
