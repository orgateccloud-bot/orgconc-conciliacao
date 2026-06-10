import { test, expect } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
import { entrarComTokenDeServico, TOKEN_SERVICO } from "./helpers";

// E2E PROFUNDO (P0 #5): erros de NEGÓCIO contra o backend real — arquivo
// corrompido, export inexistente, validação de UI e rota protegida.

const OFX_CORROMPIDO = path.join(__dirname, "fixtures", "corrompido.ofx");

test.describe("Erros de negócio (backend real)", () => {
  test("OFX corrompido: a API rejeita e a UI mostra o erro sem quebrar", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/upload");
    await page.locator('input[type="file"]').setInputFiles(OFX_CORROMPIDO);
    await page.getByRole("button", { name: "Iniciar conciliação" }).click();

    // Toast de erro (sonner) com a mensagem da API; permanece na página de upload.
    await expect(page.locator("[data-sonner-toast][data-type='error']")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page).toHaveURL(/\/app\/upload/);
    // A página continua operável (não quebrou): botão segue presente.
    await expect(page.getByRole("button", { name: "Iniciar conciliação" })).toBeVisible();
  });

  test("sem arquivos o botão de conciliação fica desabilitado", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/upload");
    await expect(page.getByRole("button", { name: "Iniciar conciliação" })).toBeDisabled();
  });

  test("export de report inexistente é rejeitado (4xx, nunca 500)", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/upload");
    const resp = await page.request.get("/export/html/rep_nao_existe", {
      headers: { Authorization: `Bearer ${TOKEN_SERVICO}` },
    });
    // 400 = formato de report_id inválido; 404 = não encontrado. Ambos são
    // rejeição de negócio correta — o que NÃO pode é 2xx/5xx.
    expect([400, 404]).toContain(resp.status());
  });

  test("auditoria forense sem CNPJ avisa e não chama a API", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/auditoria-forense");
    let chamouLaudo = false;
    page.on("request", (r) => {
      if (r.url().includes("/fiscal/laudo")) chamouLaudo = true;
    });
    await page.getByRole("button", { name: "Analisar Regime × Teto" }).click();
    await expect(page.locator("[data-sonner-toast]").first()).toBeVisible({ timeout: 10_000 });
    expect(chamouLaudo).toBe(false);
  });

  test("rota protegida sem token redireciona para o login", async ({ page }) => {
    await page.goto("/app/auditoria-forense");
    await expect(page).toHaveURL(/\/app\/login/);
  });
});
