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
      // Gate (ratchet): piso ~2-3pts abaixo do atingido em 2026-06-09 após o
      // aprofundamento (stmts 86.1 / branches 79.3 / funcs 85.6 / lines 88.6).
      // Supera o critério de 1.0 (≥80%). Trava o ganho sem fragilizar o CI.
      thresholds: {
        statements: 84,
        branches: 76,
        functions: 83,
        lines: 86,
      },
    },
  },
});
