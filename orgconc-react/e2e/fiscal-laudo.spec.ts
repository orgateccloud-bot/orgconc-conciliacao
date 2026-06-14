import { test, expect } from "@playwright/test";
import { entrarComTokenDeServico } from "./helpers";

// E2E: navegação fiscal pela sidebar (Laudo Integrado + Auditoria Forense)
// e validação de formulário do laudo SEM submeter um laudo real.
// Backend REAL (uvicorn :8765) — o /auth/me do login de serviço é de verdade.

test.describe("Fiscal: navegação sidebar → Laudo Integrado e Auditoria Forense", () => {
  test("sidebar leva ao Laudo Integrado com formulário completo", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/dashboard");

    // Grupo FISCAL da sidebar (itens são botões, não <a>).
    await page.getByRole("button", { name: "Laudo Integrado" }).click();
    await expect(page).toHaveURL(/\/app\/laudo/);

    // Elementos-chave: hero, campos do formulário e CTA no formato default (XLSX).
    await expect(
      page.getByRole("heading", { name: /Laudo Integrado/ }),
    ).toBeVisible();
    await expect(page.getByLabel("CNPJ da entidade auditada")).toBeVisible();
    await expect(page.getByLabel("Conta (opcional)")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Gerar Laudo (XLSX)" }),
    ).toBeVisible();
  });

  test("sidebar leva à Auditoria Forense com CTA de análise", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/dashboard");

    await page.getByRole("button", { name: "Auditoria Forense" }).click();
    await expect(page).toHaveURL(/\/app\/auditoria-forense/);

    // Elementos-chave: hero "Regime × teto.", campo CNPJ e os dois CTAs.
    await expect(page.getByRole("heading", { name: /Regime ×/ })).toBeVisible();
    await expect(page.getByPlaceholder("00.000.000/0000-00")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Analisar Regime × Teto" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Baixar Laudo XLSX (11 abas)" }),
    ).toBeVisible();
  });

  test("formulário do laudo valida entrada vazia sem submeter", async ({ page }) => {
    await entrarComTokenDeServico(page, "/app/laudo");

    // 1) Tudo vazio → bloqueia no CNPJ (toast de erro do sonner).
    await page.getByRole("button", { name: "Gerar Laudo (XLSX)" }).click();
    await expect(
      page.getByText("Informe o CNPJ da entidade auditada (14 dígitos)"),
    ).toBeVisible();

    // 2) CNPJ válido mas sem extrato OFX → segundo estágio da validação.
    await page
      .getByLabel("CNPJ da entidade auditada")
      .fill("11.222.333/0001-81");
    await page.getByRole("button", { name: "Gerar Laudo (XLSX)" }).click();
    await expect(page.getByText("Envie ao menos 1 extrato OFX")).toBeVisible();

    // Nada foi submetido: continua na página, com o CTA habilitado.
    await expect(page).toHaveURL(/\/app\/laudo/);
    await expect(
      page.getByRole("button", { name: "Gerar Laudo (XLSX)" }),
    ).toBeEnabled();
  });
});
