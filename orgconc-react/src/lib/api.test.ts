import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  apiFetch,
  apiRefresh,
  getToken,
  jwtExpMs,
  setToken,
} from "./api";

// JWT com exp = year 2099 (sem assinatura — apenas decode local)
const TOKEN_FUTURE =
  "eyJhbGciOiJIUzI1NiJ9." +
  btoa(JSON.stringify({ sub: "admin@x", exp: 4070908800 })) +
  ".sig";

describe("lib/api", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  describe("setToken/getToken", () => {
    it("persiste e le", () => {
      setToken("abc");
      expect(getToken()).toBe("abc");
    });

    it("setToken(null) limpa", () => {
      setToken("abc");
      setToken(null);
      expect(getToken()).toBeNull();
    });
  });

  describe("jwtExpMs", () => {
    it("retorna exp em ms para JWT valido", () => {
      const ms = jwtExpMs(TOKEN_FUTURE);
      expect(ms).toBe(4070908800 * 1000);
    });

    it("retorna null para token invalido", () => {
      expect(jwtExpMs("nao-eh-jwt")).toBeNull();
      expect(jwtExpMs(null)).toBeNull();
    });
  });

  describe("ApiError", () => {
    it("expoe status e detail", () => {
      const e = new ApiError("falhou", 503, { motivo: "x" });
      expect(e.status).toBe(503);
      expect(e.detail).toEqual({ motivo: "x" });
      expect(e.message).toBe("falhou");
    });
  });

  describe("apiRefresh", () => {
    it("seta novo token quando refresh retorna ok", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ access_token: "novo", token_type: "bearer" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      ));
      const tok = await apiRefresh();
      expect(tok).toBe("novo");
      expect(getToken()).toBe("novo");
    });

    it("retorna null quando refresh falha", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
        new Response("nope", { status: 401 })
      ));
      const tok = await apiRefresh();
      expect(tok).toBeNull();
    });
  });

  describe("apiFetch", () => {
    it("anexa Authorization quando ha token", async () => {
      setToken("xyz");
      const fetchSpy = vi.fn().mockResolvedValue(
        new Response('{"ok":true}', {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      );
      vi.stubGlobal("fetch", fetchSpy);
      await apiFetch("/v1/test");
      const call = fetchSpy.mock.calls[0];
      const headers = call[1].headers as Headers;
      expect(headers.get("Authorization")).toBe("Bearer xyz");
    });

    it("lanca ApiError em 4xx", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "bad" }), {
          status: 400,
          headers: { "content-type": "application/json" },
        })
      ));
      await expect(apiFetch("/v1/x")).rejects.toThrow(ApiError);
    });
  });
});
