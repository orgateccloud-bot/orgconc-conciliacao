import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/lib/auth";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchMe: vi.fn(),
    login: vi.fn(),
    apiLogout: vi.fn(),
  };
});

import * as api from "@/lib/api";

function TelaUsuario() {
  const { user, loading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="status">{loading ? "loading" : user ? `ok:${user.sub}` : "anon"}</span>
      <button onClick={() => login("a@b.com", "senha12345")}>entrar</button>
      <button onClick={logout}>sair</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.resetAllMocks();
  });

  it("inicia em loading e vira anon quando fetchMe falha", async () => {
    vi.mocked(api.fetchMe).mockRejectedValueOnce(new Error("401"));
    render(<AuthProvider><TelaUsuario /></AuthProvider>);
    expect(screen.getByTestId("status").textContent).toBe("loading");
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("anon"),
    );
  });

  it("login bem-sucedido seta usuario", async () => {
    vi.mocked(api.fetchMe).mockRejectedValueOnce(new Error("401"));
    vi.mocked(api.login).mockResolvedValueOnce({ access_token: "tok", token_type: "bearer" });
    vi.mocked(api.fetchMe).mockResolvedValueOnce({ sub: "user-1", role: "admin", email: "a@b.com" });

    render(<AuthProvider><TelaUsuario /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anon"));

    await act(async () => {
      screen.getByText("entrar").click();
    });

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ok:user-1"));
    expect(api.login).toHaveBeenCalledWith("a@b.com", "senha12345");
  });

  it("logout chama apiLogout e zera usuario", async () => {
    vi.mocked(api.fetchMe).mockResolvedValueOnce({ sub: "u", role: "admin" });
    vi.mocked(api.apiLogout).mockResolvedValueOnce(undefined);

    render(<AuthProvider><TelaUsuario /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ok:u"));

    await act(async () => {
      screen.getByText("sair").click();
    });

    expect(api.apiLogout).toHaveBeenCalled();
    expect(screen.getByTestId("status").textContent).toBe("anon");
  });
});
