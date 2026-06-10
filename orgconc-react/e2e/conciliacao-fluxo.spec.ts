import { test, expect } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
import { entrarComTokenDeServico, TOKEN_SERVICO } from "./helpers";

// E2E PROFUNDO (P0 #5): upload OFX → conciliação → resultado → export.
// Backend REAL (uvicorn :8765 via proxy do preview) — sem mock de rede.
// Modo "Simulação" (default da página) é determinístico: parse + anomalias
// sem LLM, então o fluxo completo roda em CI sem chave de API.

const OFX_VALIDO = path.join(__dirname, "..", "..", "tests", "fixtures", "sample.ofx");

test.describe("Fluxo completo: upload OFX → resultado da conciliação", () => {
  test("processa um OFX real em modo simulação e mostra o resultado", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/upload");
    await expect(page.getByRole("button", { name: "Iniciar conciliação" })).toBeVisible();

    // Anexa o OFX no input (hidden — setInputFiles funciona mesmo assim).
    await page.locator('input[type="file"]').setInputFiles(OFX_VALIDO);
    await expect(page.getByText("sample.ofx")).toBeVisible();

    // Modo "Simulação" já é o default; dispara a conciliação REAL.
    await page.getByRole("button", { name: "Iniciar conciliação" }).click();

    // Navega para o resultado com o report_id devolvido pela API.
    await expect(page).toHaveURL(/\/app\/conciliacao/, { timeout: 30_000 });
    await expect(page.getByText(/^ID: /)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("HTML", { exact: true })).toBeVisible();
    await expect(page.getByText("Excel", { exact: true })).toBeVisible();
  });

  test("o relatório HTML exportado responde 200 para o report gerado", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/upload");
    await page.locator('input[type="file"]').setInputFiles(OFX_VALIDO);
    await page.getByRole("button", { name: "Iniciar conciliação" }).click();
    await expect(page.getByText(/^ID: /)).toBeVisible({ timeout: 30_000 });

    const reportId = (await page.getByText(/^ID: /).innerText()).replace("ID: ", "").trim();
    expect(reportId.length).toBeGreaterThan(0);

    // Export real (mesma origem :4173 → proxy → backend), autenticado.
    const resp = await page.request.get(`/export/html/${reportId}`, {
      headers: { Authorization: `Bearer ${TOKEN_SERVICO}` },
    });
    expect(resp.status()).toBe(200);
    expect(resp.headers()["content-type"] ?? "").toContain("text/html");
    expect((await resp.text()).length).toBeGreaterThan(500);
  });
});
