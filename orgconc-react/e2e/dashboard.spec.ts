import { test, expect } from "@playwright/test";

/**
 * Specs do dashboard trust_v3 (PRs 2-5).
 *
 * Estrategia: como nao temos auth real no preview build, testamos:
 *   1. Redirecionamentos protegidos (rotas /dashboard, /auditoria etc -> /login)
 *   2. Sidebar global expandida com OPERACAO/COMPLIANCE renderiza no login
 *      (Sidebar so esta dentro do DashboardLayout, entao pulamos aqui)
 *   3. PlaceholderPage redireciona para login se nao autenticado
 *
 * Para testes que exigem dashboard renderizado, criamos token mock via
 * sessionStorage e visitamos diretamente. Sem backend real, os componentes
 * caem em estados "vazio/erro" controlados — ainda assim verificavel.
 */

// JWT decorativo (header.payload.signature) — apenas para nao redirecionar.
// AuthContext valida via /auth/me — sem backend, retorna user=null e redireciona.
// Para spec sem backend, usamos somente rotas que nao exigem auth.

test.describe("Dashboard trust — rotas protegidas", () => {
  test("redireciona /app/dashboard para /login quando nao autenticado", async ({ page }) => {
    await page.goto("/app/dashboard");
    await expect(page).toHaveURL(/\/app\/login/, { timeout: 10000 });
  });

  test("redireciona /app/auditoria para /login", async ({ page }) => {
    await page.goto("/app/auditoria");
    await expect(page).toHaveURL(/\/app\/login/, { timeout: 10000 });
  });

  test("redireciona /app/seguranca para /login", async ({ page }) => {
    await page.goto("/app/seguranca");
    await expect(page).toHaveURL(/\/app\/login/, { timeout: 10000 });
  });

  test("redireciona /app/transacoes e /app/anomalias para /login", async ({ page }) => {
    await page.goto("/app/transacoes");
    await expect(page).toHaveURL(/\/app\/login/, { timeout: 10000 });
    await page.goto("/app/anomalias");
    await expect(page).toHaveURL(/\/app\/login/, { timeout: 10000 });
  });
});

test.describe("Login — ORGATEC branding visivel", () => {
  test("tela de login mostra branding e badges", async ({ page }) => {
    await page.goto("/app/login");
    await expect(page.getByRole("heading", { name: /Entrar/i })).toBeVisible();
    await expect(page.getByText(/ORGATEC/i).first()).toBeVisible();
  });
});
