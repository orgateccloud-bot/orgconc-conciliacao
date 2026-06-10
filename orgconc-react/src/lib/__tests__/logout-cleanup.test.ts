import { describe, it, expect, beforeEach } from "vitest";
import { limparDadosTenant } from "@/lib/api";

describe("limparDadosTenant (limpeza no logout)", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  it("remove todas as chaves orgconc.* de session e localStorage", () => {
    sessionStorage.setItem("orgconc.access_token", "tok");
    sessionStorage.setItem("orgconc.last_resultado", JSON.stringify({ x: 1 }));
    localStorage.setItem("orgconc.historico.v1", "[]");

    limparDadosTenant();

    expect(sessionStorage.getItem("orgconc.access_token")).toBeNull();
    expect(sessionStorage.getItem("orgconc.last_resultado")).toBeNull();
    expect(localStorage.getItem("orgconc.historico.v1")).toBeNull();
  });

  it("preserva chaves que não são do orgconc", () => {
    localStorage.setItem("tema", "dark");
    sessionStorage.setItem("outro.app", "1");

    limparDadosTenant();

    expect(localStorage.getItem("tema")).toBe("dark");
    expect(sessionStorage.getItem("outro.app")).toBe("1");
  });
});
