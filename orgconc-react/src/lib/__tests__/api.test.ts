import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError, getToken, setToken } from "@/lib/api";

describe("apiFetch", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it("envia Authorization quando ha token", async () => {
    setToken("abc.def.ghi");
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await apiFetch("/some/path");

    const [, init] = fetchSpy.mock.calls[0];
    const headers = init?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer abc.def.ghi");
    expect(init?.credentials).toBe("include");
  });

  it("nao define Content-Type quando body eh FormData", async () => {
    const fd = new FormData();
    fd.append("file", new Blob(["x"]));
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response("{}", { status: 200, headers: { "content-type": "application/json" } }),
    );

    await apiFetch("/upload", { method: "POST", body: fd });

    const [, init] = fetchSpy.mock.calls[0];
    const headers = init?.headers as Headers;
    expect(headers.get("Content-Type")).toBeNull();
  });

  it("define Content-Type application/json para body string", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response("{}", { status: 200, headers: { "content-type": "application/json" } }),
    );

    await apiFetch("/x", { method: "POST", body: JSON.stringify({ a: 1 }) });

    const [, init] = fetchSpy.mock.calls[0];
    const headers = init?.headers as Headers;
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("401 limpa token e dispara evento orgconc:logout", async () => {
    setToken("vai-ser-limpo");
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response("", { status: 401 }),
    );
    const ouvinte = vi.fn();
    window.addEventListener("orgconc:logout", ouvinte);

    await expect(apiFetch("/me")).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBeNull();
    expect(ouvinte).toHaveBeenCalledTimes(1);

    window.removeEventListener("orgconc:logout", ouvinte);
  });

  it("status >=400 levanta ApiError com detail", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "campo invalido" }), {
        status: 400,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(apiFetch("/x")).rejects.toMatchObject({
      status: 400,
      message: "campo invalido",
    });
  });

  it("204 retorna undefined", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(null, { status: 204 }),
    );
    const out = await apiFetch("/x");
    expect(out).toBeUndefined();
  });
});
