/**
 * E2E: auditoria de acessibilidade WCAG 2.1 AA via axe-core.
 * Apenas violacoes `serious` ou `critical` falham o build.
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ROTAS_PUBLICAS = ["/app/login"];

for (const rota of ROTAS_PUBLICAS) {
  test(`acessibilidade WCAG 2.1 AA: ${rota}`, async ({ page }) => {
    await page.goto(rota);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    const serias = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );

    if (serias.length > 0) {
      console.log("Violacoes de acessibilidade:");
      for (const v of serias) {
        console.log(`  [${v.impact}] ${v.id}: ${v.description}`);
        console.log(`    -> ${v.helpUrl}`);
        for (const n of v.nodes.slice(0, 3)) {
          console.log(`    target: ${n.target.join(", ")}`);
        }
      }
    }

    expect(serias).toEqual([]);
  });
}
