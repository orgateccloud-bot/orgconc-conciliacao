/**
 * Test setup — carregado antes de cada test file pelo Vitest.
 * Configurado em vitest.config.ts via `setupFiles`.
 */
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
