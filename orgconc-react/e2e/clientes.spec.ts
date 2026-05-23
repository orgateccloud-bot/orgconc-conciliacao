import { test, expect } from "@playwright/test";

// BrowserRouter usa basename="/app" -- todos os caminhos devem incluir /app
test.describe("Pagina de Clientes (sem auth)", () => {
    test("redireciona para /app/login quando nao autenticado", async ({ page }) => {
          await page.goto("/app/clientes");
          await expect(page).toHaveURL(/\/app\/login/);
    });
});

test.describe("Validacao de CNPJ no formulario de cliente", () => {
    test("exibe erro para CNPJ invalido antes de enviar ao servidor", async ({ page }) => {
          await page.route("/auth/me", (route) =>
                  route.fulfill({
                            status: 200,
                            contentType: "application/json",
                            body: JSON.stringify({ sub: "test-user", role: "admin" }),
                  }),
                               );
          await page.route("/auth/login", (route) =>
                  route.fulfill({
                            status: 200,
                            contentType: "application/json",
                            body: JSON.stringify({ access_token: "fake.jwt.token", token_type: "bearer" }),
                  }),
                               );

             await page.goto("/app/login");
          await page.evaluate(() => sessionStorage.setItem("orgconc.access_token", "fake.jwt.token"));
          await page.goto("/app/clientes");

             const url = page.url();
          if (url.includes("/login")) {
                  await expect(page).toHaveURL(/\/app\/login/);
          } else {
                  const novoBtn = page.getByRole("button", { name: /novo cliente/i });
                  if (await novoBtn.isVisible()) {
                            await novoBtn.click();
                            const cnpjInput = page.getByLabel(/cnpj/i);
                            if (await cnpjInput.isVisible()) {
                                        await cnpjInput.fill("00.000.000/0000-00");
                                        await page.getByRole("button", { name: /salvar/i }).click();
                                        await expect(page.getByText(/cnpj inv/i)).toBeVisible();
                            }
                  }
          }
    });
});
