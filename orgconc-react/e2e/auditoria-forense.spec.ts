import { test, expect } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
import { entrarComTokenDeServico, TOKEN_SERVICO } from "./helpers";

// E2E PROFUNDO (P0 #5): fluxo de auditoria forense (regime × teto) com backend
// REAL. A fixture forense.ofx é sintética, com memos SEM CNPJ — o pipeline não
// dispara enriquecimento BrasilAPI (zero rede externa, estável em CI). EMPRESA
// é montada cache-only a partir do CNPJ informado.

const OFX_FORENSE = path.join(__dirname, "fixtures", "forense.ofx");
const CNPJ = "11.222.333/0001-81"; // DV válido; sintético (sem cache → campos "—")

test.describe("Auditoria forense: OFX → resumo regime × teto", () => {
  test("analisa o extrato e exibe o resumo forense", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/auditoria-forense");
    await expect(
      page.getByRole("button", { name: "Analisar Regime × Teto" }),
    ).toBeVisible();

    await page.getByPlaceholder("00.000.000/0000-00").fill(CNPJ);
    await page.locator('input[type="file"]').setInputFiles(OFX_FORENSE);
    await expect(page.getByText("forense.ofx")).toBeVisible();

    await page.getByRole("button", { name: "Analisar Regime × Teto" }).click();

    // O resumo REAL chega: card da empresa (situação · porte) + período derivado
    // dos dados (jan→mar 2026). Botão volta do estado "Analisando...".
    await expect(page.getByText(/· porte/)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/Período: 2026-01/)).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Analisar Regime × Teto" }),
    ).toBeEnabled();
  });

  test("baixa o laudo XLSX de 11 abas do mesmo extrato", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/auditoria-forense");
    await page.getByPlaceholder("00.000.000/0000-00").fill(CNPJ);
    await page.locator('input[type="file"]').setInputFiles(OFX_FORENSE);

    const download = page.waitForEvent("download", { timeout: 120_000 });
    await page
      .getByRole("button", { name: "Baixar Laudo XLSX (11 abas)" })
      .click();
    const arquivo = await download;
    expect(arquivo.suggestedFilename()).toMatch(/\.xlsx$/i);
  });

  test("POST /fiscal/laudo/resumo responde JSON coerente para o extrato", async ({ page }) => {
    // Prova de contrato da API real (sem UI): mesmo payload do fluxo acima.
    await entrarComTokenDeServico(page, "/app/auditoria-forense");
    const fs = await import("fs");
    const resp = await page.request.post("/fiscal/laudo/resumo", {
      headers: { Authorization: `Bearer ${TOKEN_SERVICO}` },
      multipart: {
        empresa_cnpj: "11222333000181",
        conta: "",
        arquivos: {
          name: "forense.ofx",
          mimeType: "application/octet-stream",
          buffer: fs.readFileSync(OFX_FORENSE),
        },
      },
    });
    expect(resp.status()).toBe(200);
    const corpo = await resp.json();
    expect(corpo.empresa.cnpj).toContain("11.222.333/0001-81");
    expect(corpo.regime).toBeTruthy();
    expect(corpo.periodo.inicio).toContain("2026-01");
    expect(corpo.enriquecimento_pendente).toBe(0); // memos sem CNPJ → sem BrasilAPI
  });
});
