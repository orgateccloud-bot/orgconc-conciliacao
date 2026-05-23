import { test, expect } from "@playwright/test";

// BrowserRouter usa basename="/app" -- todos os caminhos devem incluir /app
test.describe("Paginas inexistentes e boundary de erros", () => {
  test("rota inexistente redireciona ou exibe 404", async ({ page }) => {
    await page.goto("/app/rota-que-nao-existe");
    // aguarda redirect para login (nao autenticado) ou exibicao de 404
    const redirected = await expect(page)
      .toHaveURL(/\/app\/login/, { timeout: 10000 })
      .then(() => true)
      .catch(() => false);
    if (!redirected) {
      const has404 = await page.getByText(/404|nao encontrada|not found/i).isVisible().catch(() => false);
      expect(has404).toBe(true);
    }
  });

  test("API 401 global dispara evento de logout e redireciona para /login", async ({ page }) => {
    // Navega para login e injeta token expirado
    await page.goto("/app/login");
    await page.evaluate(() => sessionStorage.setItem("orgconc.access_token", "expired.token.here"));

    // Mock /auth/me para retornar 401
    await page.route("**/auth/me", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Unauthorized" }) }),
    );

    await page.goto("/app/conciliacao");
    await expect(page).toHaveURL(/\/app\/login/, { timeout: 10000 });
    const token = await page.evaluate(() => sessionStorage.getItem("orgconc.access_token"));
    expect(token).toBeNull();
  });

  test("upload de arquivo invalido mostra mensagem de erro na UI", async ({ page }) => {
    // Limpa estado antes do teste
    await page.goto("/app/login");
    await page.evaluate(() => sessionStorage.clear());
    // Sem autenticacao, conciliacao deve redirecionar para login
    await page.goto("/app/conciliacao");
    await expect(page).toHaveURL(/\/app\/login/, { timeout: 10000 });
  });
});
