/**
 * E2E: health endpoints da API.
 * Independem de auth ou DB — deveriam funcionar sempre.
 */
import { test, expect, request as pwRequest } from "@playwright/test";

test.describe("Health endpoints", () => {
  test("/health/live retorna 200", async () => {
    const api = await pwRequest.newContext();
    const res = await api.get("/health/live");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  test("/health retorna estrutura completa", async () => {
    const api = await pwRequest.newContext();
    const res = await api.get("/health");
    // 200 ou 503 — dependendo se DB esta up — mas estrutura mesma
    expect([200, 503]).toContain(res.status());
    const body = await res.json();
    expect(body).toHaveProperty("versao");
    expect(body).toHaveProperty("uptime_s");
    expect(body).toHaveProperty("dependencies");
    expect(body.dependencies).toHaveProperty("database");
    expect(body.dependencies).toHaveProperty("anthropic");
  });

  test("/ lista endpoints v1", async () => {
    const api = await pwRequest.newContext();
    const res = await api.get("/");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.endpoints.join(" ")).toMatch(/\/v1\/conciliar\/ofx/);
    expect(body.endpoints.join(" ")).toMatch(/\/v1\/clientes/);
  });
});
