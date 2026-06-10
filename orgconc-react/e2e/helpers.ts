import type { Page } from "@playwright/test";

/** Token de serviço usado pelo backend dos E2E (ORGCONC_AUTH_TOKEN no CI). */
export const TOKEN_SERVICO = "e2e-ci-token";

/**
 * Autentica via token de serviço REAL contra o backend (sem mock de rede):
 * grava o Bearer no sessionStorage ANTES de qualquer script da página
 * (addInitScript roda em toda navegação). O AuthProvider chama GET /auth/me
 * de verdade (role "service") e o ProtectedRoute libera.
 *
 * Por que não setItem após goto: o fetchMe inicial (sem token) do primeiro
 * load ainda está em voo; ao resolver 401, o catch do AuthProvider vê o token
 * recém-gravado e o APAGA (setToken(null)) — corrida real flagrada no debug.
 */
export async function entrarComTokenDeServico(page: Page, destino: string) {
  await page.addInitScript(
    (t) => sessionStorage.setItem("orgconc.access_token", t),
    TOKEN_SERVICO,
  );
  await page.goto(destino);
}
