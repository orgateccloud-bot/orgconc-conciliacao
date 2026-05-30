/**
 * E2E: API /v1/jobs (item 13).
 * Requer auth + DB + Redis + worker. Skipa se ANY dep down.
 */
import { test, expect, request as pwRequest } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "";
const ADMIN_PASS = process.env.E2E_ADMIN_PASS || "";

test.describe("API /v1/jobs", () => {
  test.beforeAll(async () => {
    test.skip(!ADMIN_EMAIL || !ADMIN_PASS, "E2E_ADMIN_EMAIL/PASS nao configurados");
  });

  test("enfileira ping e retorna 202", async () => {
    const api = await pwRequest.newContext();
    const login = await api.post("/auth/login", {
      data: { email: ADMIN_EMAIL, senha: ADMIN_PASS },
    });
    test.skip(login.status() !== 200, "Auth nao disponivel (DB?)");
    const { access_token } = await login.json();

    const enqueue = await api.post("/v1/jobs", {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { tipo: "ping", input: { mensagem: "hello" } },
    });
    // Pode ser 202 (ok) ou 503 (sem Redis); ambos sao toleraveis nesse smoke
    if (enqueue.status() === 503) {
      test.skip(true, "Redis indisponivel — jobs desativados");
    }
    expect(enqueue.status()).toBe(202);
    const body = await enqueue.json();
    expect(body).toHaveProperty("id");
    expect(body.status).toBe("queued");
    expect(body.polling_url).toMatch(/^\/v1\/jobs\//);
  });
});
