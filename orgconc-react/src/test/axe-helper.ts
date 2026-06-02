import axe, { type AxeResults, type RunOptions } from "axe-core";

const DEFAULT_RULES: RunOptions = {
  runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
};

export async function auditarA11y(element: Element, options: RunOptions = DEFAULT_RULES): Promise<AxeResults> {
  return await axe.run(element, options);
}

export function semViolacoesCriticas(results: AxeResults): boolean {
  const criticas = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  );
  if (criticas.length > 0) {
    console.error(
      "Violacoes a11y criticas:\n" +
        criticas
          .map((v) => `  [${v.impact}] ${v.id}: ${v.description}\n    ${v.helpUrl}`)
          .join("\n"),
    );
  }
  return criticas.length === 0;
}
