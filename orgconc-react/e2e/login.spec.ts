import { test, expect } from "@playwright/test";

test.describe("Pagina de login", () => {
  test("exibe formulario de autenticacao", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading")).toContainText("ORGATEC");
    await expect(page.getByLabel("E-mail")).toBeVisible();
    await expect(page.getByLabel("Senha")).toBeVisible();
    await expect(page.getByRole("button", { name: "Entrar" })).toBeVisible();
  });

  test("bloqueia submit com senha curta", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("E-mail").fill("admin@test.com");
    await page.getByLabel("Senha").fill("123");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page.getByText(/pelo menos 8/i)).toBeVisible();
  });

  test("redireciona para /login quando nao autenticado", async ({ page }) => {
    await page.goto("/conciliacao");
    await expect(page).toHaveURL(/\/login/);
  });

  test("redireciona raiz para /login quando nao autenticado", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });
});
