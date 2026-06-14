import { test, expect } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
import { entrarComTokenDeServico } from "./helpers";

// E2E: upload OFX → resultado da conciliação (scorecard: fluxo upload→resultado).
// Backend REAL (uvicorn :8765 via proxy do preview) — sem mock de rede.
// Modo "Simulação" (default da página) é determinístico: parse + anomalias
// sem LLM, então roda em CI sem chave de API real.
//
// Fixture própria (extrato-mini.ofx, 4 transações no formato OFX SGML do
// OFX_SAMPLE de tests/test_api.py) com tarifa duplicada — o total de
// transações no KPI é previsível (4).

const OFX_MINI = path.join(__dirname, "fixtures", "extrato-mini.ofx");

test.describe("Upload → resultado: report_id, KPIs e exports", () => {
  test("processa o OFX em modo simulação e mostra ID, KPIs e botões de export", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/upload");
    await expect(
      page.getByRole("button", { name: "Iniciar conciliação" }),
    ).toBeVisible();

    // Anexa o OFX no input (hidden — setInputFiles funciona mesmo assim).
    await page.locator('input[type="file"]').setInputFiles(OFX_MINI);
    await expect(page.getByText("extrato-mini.ofx")).toBeVisible();

    // Modo "Simulação" já é o default; dispara a conciliação REAL.
    await page.getByRole("button", { name: "Iniciar conciliação" }).click();

    // Resultado: navega para /app/conciliacao com o report_id devolvido pela API.
    await expect(page).toHaveURL(/\/app\/conciliacao/, { timeout: 30_000 });
    const idLinha = page.getByText(/^ID: /);
    await expect(idLinha).toBeVisible({ timeout: 15_000 });
    const reportId = (await idLinha.innerText()).replace("ID: ", "").trim();
    expect(reportId.length).toBeGreaterThan(0);

    // KPIs pós-conciliação: total de transações bate com a fixture (4),
    // anomalias e modo (badge "Simulação") presentes.
    await expect(
      page.getByText("Total Transações").locator(".."),
    ).toContainText("4");
    await expect(page.getByText("Total Anomalias")).toBeVisible();
    await expect(page.getByText("Simulação", { exact: true })).toBeVisible();

    // Exports são BOTÕES (download autenticado via Bearer), não links.
    for (const nome of ["HTML", "Excel", "PDF"]) {
      await expect(
        page.getByRole("button", { name: nome, exact: true }),
      ).toBeVisible();
    }
    await expect(page.getByRole("link", { name: "PDF" })).toHaveCount(0);
  });
});
