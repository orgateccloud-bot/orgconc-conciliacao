import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  apiFetch,
  apiFetchBlob,
  apiLogout,
  apiRefresh,
  atualizarCliente,
  carregarHistoricoLocal,
  conciliarCsv,
  conciliarMatchers,
  conciliarOfx,
  criarCliente,
  criarContrato,
  criarGuia,
  criarOrg,
  criarUsuario,
  fetchActivityFeed,
  fetchAiInsights,
  fetchAuditEvento,
  fetchAuditTimeline,
  fetchDashboardBundle,
  fetchHealth,
  fetchMe,
  fetchTrustScore,
  fiscalConformidade,
  fiscalGerarCarta,
  fiscalLaudo,
  fiscalLaudoBlob,
  fiscalLaudoResumo,
  fiscalListarCartas,
  fiscalProcessar,
  fiscalRiscoTributario,
  getToken,
  invalidarCacheClientes,
  listarClientes,
  listarConciliacoes,
  listarConciliacoesDoCliente,
  listarContratos,
  listarGuias,
  listarOrgs,
  listarUsuarios,
  login,
  resetarSenhaUsuario,
  salvarHistoricoLocal,
  setToken,
} from "@/lib/api";
import type {
  Cliente,
  ConciliacaoResponse,
  Contrato,
  Guia,
  MatchersResponse,
  UserMe,
} from "@/lib/api";

// ── helpers ────────────────────────────────────────────────────────────────

/** Cria uma Response JSON 200 (ok). */
function jsonOk(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
    ...init,
  });
}

/** Stub do fetch global devolvendo as respostas dadas na ordem. */
function stubFetch(...responses: Response[]) {
  const fn = vi.fn();
  responses.forEach((r) => fn.mockResolvedValueOnce(r));
  vi.stubGlobal("fetch", fn);
  return fn;
}

/** Última URL e init com que o fetch foi chamado (índice opcional). */
function callAt(fn: ReturnType<typeof vi.fn>, i = 0): [string, RequestInit | undefined] {
  const c = fn.mock.calls[i];
  return [c[0] as string, c[1] as RequestInit | undefined];
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  invalidarCacheClientes();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
  localStorage.clear();
});

// ── token helpers ────────────────────────────────────────────────────────────

describe("token helpers", () => {
  it("setToken/getToken persistem e limpam no sessionStorage", () => {
    expect(getToken()).toBeNull();
    setToken("xyz");
    expect(getToken()).toBe("xyz");
    setToken(null);
    expect(getToken()).toBeNull();
  });
});

// ── auth / sessão ────────────────────────────────────────────────────────────

describe("apiLogout", () => {
  it("chama POST /auth/logout e limpa o token mesmo com falha de rede", async () => {
    setToken("a-limpar");
    const fn = stubFetch(new Response("", { status: 200 }));
    await apiLogout();
    const [url, init] = callAt(fn);
    expect(url).toBe("/auth/logout");
    expect(init?.method).toBe("POST");
    expect(init?.credentials).toBe("include");
    expect(getToken()).toBeNull();
  });

  it("limpa o token via finally mesmo se o fetch rejeitar", async () => {
    setToken("a-limpar");
    const fn = vi.fn().mockRejectedValueOnce(new Error("rede caiu"));
    vi.stubGlobal("fetch", fn);
    // O finally limpa o token; a rejeição da rede ainda propaga (sem catch).
    await expect(apiLogout()).rejects.toThrow("rede caiu");
    expect(getToken()).toBeNull();
  });
});

describe("apiRefresh", () => {
  it("retorna o novo access_token e o persiste", async () => {
    stubFetch(jsonOk({ access_token: "novo-token" }));
    const out = await apiRefresh();
    expect(out).toBe("novo-token");
    expect(getToken()).toBe("novo-token");
  });

  it("retorna null quando a resposta não é ok", async () => {
    stubFetch(new Response("", { status: 401 }));
    expect(await apiRefresh()).toBeNull();
  });

  it("retorna null quando o corpo não traz access_token", async () => {
    stubFetch(jsonOk({}));
    expect(await apiRefresh()).toBeNull();
  });

  it("retorna null quando o fetch rejeita", async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error("boom"));
    vi.stubGlobal("fetch", fn);
    expect(await apiRefresh()).toBeNull();
  });
});

describe("fetchHealth", () => {
  it("faz GET /health e devolve o JSON", async () => {
    const fn = stubFetch(jsonOk({ status: "ok", banco_dados: "online" }));
    const out = await fetchHealth();
    const [url, init] = callAt(fn);
    expect(url).toBe("/health");
    expect(init?.credentials).toBe("include");
    expect(out.status).toBe("ok");
    expect(out.banco_dados).toBe("online");
  });
});

// ── apiFetch: caminhos de parse / erro ───────────────────────────────────────

describe("apiFetch parse e erros", () => {
  it("devolve texto quando o content-type não é JSON", async () => {
    stubFetch(new Response("texto puro", { status: 200, headers: { "content-type": "text/plain" } }));
    const out = await apiFetch<string>("/x");
    expect(out).toBe("texto puro");
  });

  it("lança ApiError com 'Erro {status}' quando detail não tem campo detail", async () => {
    stubFetch(jsonOk({ erro: "qualquer" }, { status: 500 }));
    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 500, message: "Erro 500" });
  });

  it("lança ApiError 'Erro {status}' em corpo de erro vazio", async () => {
    stubFetch(new Response(null, { status: 503 }));
    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 503, message: "Erro 503" });
  });

  it("ApiError carrega status e detail", async () => {
    stubFetch(jsonOk({ detail: "proibido" }, { status: 403 }));
    try {
      await apiFetch("/x");
      throw new Error("deveria ter lançado");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).status).toBe(403);
      expect((e as ApiError).detail).toEqual({ detail: "proibido" });
    }
  });

  it("não tenta refresh quando path é /auth/refresh (evita loop)", async () => {
    setToken("t");
    const fn = stubFetch(new Response("", { status: 401 }));
    await expect(apiFetch("/auth/refresh")).rejects.toBeInstanceOf(ApiError);
    // Apenas a request original; sem 2ª chamada de refresh.
    expect(fn).toHaveBeenCalledTimes(1);
    expect(getToken()).toBeNull();
  });
});

// ── apiFetchBlob ─────────────────────────────────────────────────────────────

describe("apiFetchBlob", () => {
  it("devolve blob e extrai filename do content-disposition", async () => {
    const fn = stubFetch(
      new Response("binario", {
        status: 200,
        headers: { "content-disposition": 'attachment; filename="rel.xlsx"' },
      }),
    );
    setToken("tk");
    const { blob, filename } = await apiFetchBlob("/fiscal/laudo", { method: "POST" });
    // Blob vem de response.blob() (undici/Node), realm diferente do Blob do jsdom
    // no CI Node 22 — toBeInstanceOf(Blob) falha. Checagem cross-realm via tag.
    expect(Object.prototype.toString.call(blob)).toBe("[object Blob]");
    expect(filename).toBe("rel.xlsx");
    const [, init] = callAt(fn);
    expect((init?.headers as Headers).get("Authorization")).toBe("Bearer tk");
  });

  it("filename null quando não há content-disposition", async () => {
    stubFetch(new Response("bin", { status: 200 }));
    const { filename } = await apiFetchBlob("/x");
    expect(filename).toBeNull();
  });

  it("ignora filename*= (RFC 5987) e retorna null", async () => {
    stubFetch(
      new Response("bin", {
        status: 200,
        headers: { "content-disposition": "attachment; filename*=UTF-8''rel%20fiscal.xlsx" },
      }),
    );
    const { filename } = await apiFetchBlob("/x");
    expect(filename).toBeNull();
  });

  it("lança ApiError em resposta !ok", async () => {
    stubFetch(jsonOk({ detail: "sem permissao" }, { status: 403 }));
    await expect(apiFetchBlob("/x")).rejects.toMatchObject({ status: 403, message: "sem permissao" });
  });

  it("faz refresh-on-401 e refaz a request com o novo token", async () => {
    setToken("velho");
    const fn = stubFetch(
      new Response("", { status: 401 }),
      jsonOk({ access_token: "blob-novo" }),
      new Response("ok-bin", { status: 200 }),
    );
    const { blob } = await apiFetchBlob("/dl");
    // Blob vem de response.blob() (undici/Node), realm diferente do Blob do jsdom
    // no CI Node 22 — toBeInstanceOf(Blob) falha. Checagem cross-realm via tag.
    expect(Object.prototype.toString.call(blob)).toBe("[object Blob]");
    expect(getToken()).toBe("blob-novo");
    expect(fn).toHaveBeenCalledTimes(3);
    const retryHeaders = fn.mock.calls[2][1]?.headers as Headers;
    expect(retryHeaders.get("Authorization")).toBe("Bearer blob-novo");
  });

  it("401 sem refresh limpa token e dispara orgconc:logout", async () => {
    setToken("velho");
    stubFetch(new Response("", { status: 401 }), new Response("", { status: 401 }));
    const ouvinte = vi.fn();
    window.addEventListener("orgconc:logout", ouvinte);
    await expect(apiFetchBlob("/dl")).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBeNull();
    expect(ouvinte).toHaveBeenCalledTimes(1);
    window.removeEventListener("orgconc:logout", ouvinte);
  });
});

// ── auth endpoints ───────────────────────────────────────────────────────────

describe("login / fetchMe", () => {
  it("login faz POST /auth/login com email e senha", async () => {
    const fn = stubFetch(jsonOk({ access_token: "tok", token_type: "bearer" }));
    const out = await login("a@b.com", "segredo");
    const [url, init] = callAt(fn);
    expect(url).toBe("/auth/login");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ email: "a@b.com", senha: "segredo" });
    expect(out.access_token).toBe("tok");
  });

  it("fetchMe faz GET /auth/me", async () => {
    const fn = stubFetch(jsonOk({ sub: "u1", role: "admin" } satisfies UserMe));
    const out = await fetchMe();
    const [url, init] = callAt(fn);
    expect(url).toBe("/auth/me");
    expect(init?.method).toBeUndefined();
    expect(out.role).toBe("admin");
  });
});

// ── conciliação (multipart) ──────────────────────────────────────────────────

describe("conciliarOfx / conciliarCsv", () => {
  const file = new File(["x"], "ex.ofx");

  it("conciliarOfx: simular=true tem prioridade na query", async () => {
    const fn = stubFetch(jsonOk({ modo: "sim" } as ConciliacaoResponse));
    await conciliarOfx([file], { simular: true, multi_modelo: true });
    const [url, init] = callAt(fn);
    expect(url).toBe("/conciliar/ofx?simular=true");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
  });

  it("conciliarOfx: multi_modelo quando não simula", async () => {
    const fn = stubFetch(jsonOk({} as ConciliacaoResponse));
    await conciliarOfx([file], { multi_modelo: true });
    expect(callAt(fn)[0]).toBe("/conciliar/ofx?multi_modelo=true");
  });

  it("conciliarOfx: modelo específico", async () => {
    const fn = stubFetch(jsonOk({} as ConciliacaoResponse));
    await conciliarOfx([file], { modelo: "gpt-x" });
    expect(callAt(fn)[0]).toBe("/conciliar/ofx?modelo=gpt-x");
  });

  it("conciliarOfx: sem opções não acrescenta query", async () => {
    const fn = stubFetch(jsonOk({} as ConciliacaoResponse));
    await conciliarOfx([file], {});
    expect(callAt(fn)[0]).toBe("/conciliar/ofx");
  });

  it("conciliarCsv: POST /conciliar/csv com modelo", async () => {
    const fn = stubFetch(jsonOk({} as ConciliacaoResponse));
    await conciliarCsv([new File(["y"], "e.csv")], { modelo: "m1" });
    const [url, init] = callAt(fn);
    expect(url).toBe("/conciliar/csv?modelo=m1");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
  });
});

describe("conciliarMatchers", () => {
  it("POST /matchers/conciliar com FormData (cliente_id + arquivos)", async () => {
    const fn = stubFetch(jsonOk({ cliente_id: "c1", total_transacoes: 5 } as MatchersResponse));
    const out = await conciliarMatchers("c1", [new File(["x"], "a.ofx")]);
    const [url, init] = callAt(fn);
    expect(url).toBe("/matchers/conciliar");
    expect(init?.method).toBe("POST");
    const fd = init?.body as FormData;
    expect(fd.get("cliente_id")).toBe("c1");
    expect(out.cliente_id).toBe("c1");
  });
});

// ── clientes (+cache) ────────────────────────────────────────────────────────

describe("clientes", () => {
  it("listarClientes faz GET /clientes e cacheia (2ª chamada não refetch)", async () => {
    const fn = stubFetch(jsonOk([{ id: "1", nome: "A", plano: "free" }] as Cliente[]));
    const a = await listarClientes();
    const b = await listarClientes();
    expect(a).toEqual(b);
    expect(callAt(fn)[0]).toBe("/clientes");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("invalidarCacheClientes força novo fetch", async () => {
    const fn = stubFetch(
      jsonOk([{ id: "1", nome: "A", plano: "free" }] as Cliente[]),
      jsonOk([{ id: "2", nome: "B", plano: "pro" }] as Cliente[]),
    );
    await listarClientes();
    invalidarCacheClientes();
    const segunda = await listarClientes();
    expect(segunda[0].id).toBe("2");
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("criarCliente faz POST /clientes com JSON", async () => {
    const fn = stubFetch(jsonOk({ id: "9", nome: "Novo", plano: "free" } as Cliente));
    const out = await criarCliente({ nome: "Novo" });
    const [url, init] = callAt(fn);
    expect(url).toBe("/clientes");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ nome: "Novo" });
    expect(out.id).toBe("9");
  });

  it("atualizarCliente faz PATCH /clientes/:id", async () => {
    const fn = stubFetch(jsonOk({ id: "9", nome: "Edit", plano: "pro" } as Cliente));
    await atualizarCliente("9", { nome: "Edit" });
    const [url, init] = callAt(fn);
    expect(url).toBe("/clientes/9");
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(init?.body as string)).toEqual({ nome: "Edit" });
  });
});

// ── conciliações ─────────────────────────────────────────────────────────────

describe("conciliações", () => {
  it("listarConciliacoes sem cliente_id", async () => {
    const fn = stubFetch(jsonOk([]));
    await listarConciliacoes();
    expect(callAt(fn)[0]).toBe("/conciliacoes");
  });

  it("listarConciliacoes com cliente_id na query", async () => {
    const fn = stubFetch(jsonOk([]));
    await listarConciliacoes("c42");
    expect(callAt(fn)[0]).toBe("/conciliacoes?cliente_id=c42");
  });

  it("listarConciliacoesDoCliente usa rota por-cliente", async () => {
    const fn = stubFetch(jsonOk([]));
    await listarConciliacoesDoCliente("c7");
    expect(callAt(fn)[0]).toBe("/conciliacoes/por-cliente/c7");
  });
});

// ── histórico local ──────────────────────────────────────────────────────────

describe("histórico local", () => {
  it("salvar e carregar fazem roundtrip via localStorage", () => {
    expect(carregarHistoricoLocal()).toEqual([]);
    const entry = { id: "1", modo: "ofx", ts: "2026-01-01", total_tx: 3, total_anom: 1 };
    salvarHistoricoLocal(entry);
    const hist = carregarHistoricoLocal();
    expect(hist).toHaveLength(1);
    expect(hist[0]).toEqual(entry);
  });

  it("carregarHistoricoLocal devolve [] quando o JSON está corrompido", () => {
    localStorage.setItem("orgconc.historico.v1", "{nao-e-json");
    expect(carregarHistoricoLocal()).toEqual([]);
  });

  it("mantém no máximo 30 entradas", () => {
    for (let i = 0; i < 35; i++) {
      salvarHistoricoLocal({ id: String(i), modo: "ofx", ts: "t", total_tx: 0, total_anom: 0 });
    }
    const hist = carregarHistoricoLocal();
    expect(hist).toHaveLength(30);
    expect(hist[0].id).toBe("5");
    expect(hist[29].id).toBe("34");
  });
});

// ── guias / contratos ────────────────────────────────────────────────────────

describe("guias e contratos", () => {
  it("listarGuias sem clienteId", async () => {
    const fn = stubFetch(jsonOk([] as Guia[]));
    await listarGuias();
    expect(callAt(fn)[0]).toBe("/guias");
  });

  it("listarGuias com clienteId", async () => {
    const fn = stubFetch(jsonOk([] as Guia[]));
    await listarGuias("c1");
    expect(callAt(fn)[0]).toBe("/guias?cliente_id=c1");
  });

  it("criarGuia faz POST /guias com JSON", async () => {
    const fn = stubFetch(jsonOk({ id: "g1" } as Guia));
    await criarGuia({ cliente_id: "c1", tipo: "DARF", valor: 100 });
    const [url, init] = callAt(fn);
    expect(url).toBe("/guias");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toMatchObject({ cliente_id: "c1", tipo: "DARF", valor: 100 });
  });

  it("listarContratos com clienteId", async () => {
    const fn = stubFetch(jsonOk([] as Contrato[]));
    await listarContratos("c1");
    expect(callAt(fn)[0]).toBe("/contratos?cliente_id=c1");
  });

  it("criarContrato faz POST /contratos com JSON", async () => {
    const fn = stubFetch(jsonOk({ id: "k1" } as Contrato));
    await criarContrato({ cliente_id: "c1", descricao: "Aluguel", valor: 500 });
    const [url, init] = callAt(fn);
    expect(url).toBe("/contratos");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toMatchObject({ descricao: "Aluguel", valor: 500 });
  });
});

// ── fiscal ───────────────────────────────────────────────────────────────────

describe("fiscal", () => {
  const ofx = new File(["x"], "e.ofx");

  it("fiscalProcessar: POST /fiscal/processar com FormData (sem enrich_all)", async () => {
    const fn = stubFetch(jsonOk({ cliente_id: "c1", documentos_processados: 2 }));
    await fiscalProcessar("c1", [ofx]);
    const [url, init] = callAt(fn);
    expect(url).toBe("/fiscal/processar");
    expect(init?.method).toBe("POST");
    const fd = init?.body as FormData;
    expect(fd.get("cliente_id")).toBe("c1");
    expect(fd.get("enrich_all")).toBeNull();
  });

  it("fiscalProcessar: inclui enrich_all quando true", async () => {
    const fn = stubFetch(jsonOk({ cliente_id: "c1" }));
    await fiscalProcessar("c1", [ofx], true);
    const fd = callAt(fn)[1]?.body as FormData;
    expect(fd.get("enrich_all")).toBe("true");
  });

  it("fiscalConformidade sem classe_minima", async () => {
    const fn = stubFetch(jsonOk({ cliente_id: "c1", total: 0, fornecedores: [] }));
    await fiscalConformidade("c1");
    expect(callAt(fn)[0]).toBe("/fiscal/conformidade/c1");
  });

  it("fiscalConformidade com classe_minima", async () => {
    const fn = stubFetch(jsonOk({ cliente_id: "c1", total: 0, fornecedores: [] }));
    await fiscalConformidade("c1", "ALTO");
    expect(callAt(fn)[0]).toBe("/fiscal/conformidade/c1?classe_minima=ALTO");
  });

  it("fiscalRiscoTributario faz GET /fiscal/risco-tributario/:id", async () => {
    const fn = stubFetch(jsonOk({ cliente_id: "c1", risco_total_anual: 0 }));
    await fiscalRiscoTributario("c1");
    expect(callAt(fn)[0]).toBe("/fiscal/risco-tributario/c1");
  });

  it("fiscalGerarCarta faz POST /fiscal/gerar-carta/:id", async () => {
    const fn = stubFetch(jsonOk({ cliente_id: "c1", markdown: "## carta" }));
    const out = await fiscalGerarCarta("c1");
    const [url, init] = callAt(fn);
    expect(url).toBe("/fiscal/gerar-carta/c1");
    expect(init?.method).toBe("POST");
    expect(out.markdown).toBe("## carta");
  });

  it("fiscalListarCartas faz GET /fiscal/cartas/:id", async () => {
    const fn = stubFetch(jsonOk({ cliente_id: "c1", total: 0, cartas: [] }));
    await fiscalListarCartas("c1");
    expect(callAt(fn)[0]).toBe("/fiscal/cartas/c1");
  });

  it("fiscalLaudoResumo: POST /fiscal/laudo/resumo com FormData", async () => {
    const fn = stubFetch(jsonOk({ n_transacoes: 7 }));
    const out = await fiscalLaudoResumo("00.000.000/0001-00", "12345", [ofx]);
    const [url, init] = callAt(fn);
    expect(url).toBe("/fiscal/laudo/resumo");
    expect(init?.method).toBe("POST");
    const fd = init?.body as FormData;
    expect(fd.get("empresa_cnpj")).toBe("00.000.000/0001-00");
    expect(fd.get("conta")).toBe("12345");
    expect(out.n_transacoes).toBe(7);
  });

  it("fiscalLaudoBlob: POST /fiscal/laudo via apiFetchBlob", async () => {
    const fn = stubFetch(
      new Response("bin", {
        status: 200,
        headers: { "content-disposition": 'attachment; filename="laudo.xlsx"' },
      }),
    );
    const { blob, filename } = await fiscalLaudoBlob("CNPJ", "999", [ofx]);
    // Blob vem de response.blob() (undici/Node), realm diferente do Blob do jsdom
    // no CI Node 22 — toBeInstanceOf(Blob) falha. Checagem cross-realm via tag.
    expect(Object.prototype.toString.call(blob)).toBe("[object Blob]");
    expect(filename).toBe("laudo.xlsx");
    const [url, init] = callAt(fn);
    expect(url).toBe("/fiscal/laudo");
    expect((init?.body as FormData).get("conta")).toBe("999");
  });
});

// ── fiscalLaudo (download direto com refresh manual) ─────────────────────────

describe("fiscalLaudo", () => {
  const ofx = new File(["x"], "e.ofx");

  it("POST /fiscal/laudo?formato=xlsx e extrai filename do header", async () => {
    setToken("tk");
    const fn = stubFetch(
      new Response("bin", {
        status: 200,
        headers: { "content-disposition": 'attachment; filename="meu-laudo.xlsx"' },
      }),
    );
    const { blob, filename } = await fiscalLaudo({
      empresaCnpj: "CNPJ",
      conta: "111",
      arquivos: [ofx],
      formato: "xlsx",
    });
    // Blob vem de response.blob() (undici/Node), realm diferente do Blob do jsdom
    // no CI Node 22 — toBeInstanceOf(Blob) falha. Checagem cross-realm via tag.
    expect(Object.prototype.toString.call(blob)).toBe("[object Blob]");
    expect(filename).toBe("meu-laudo.xlsx");
    const [url, init] = callAt(fn);
    expect(url).toBe("/fiscal/laudo?formato=xlsx");
    expect(init?.method).toBe("POST");
    expect((init?.headers as Headers).get("Authorization")).toBe("Bearer tk");
    const fd = init?.body as FormData;
    expect(fd.get("empresa_cnpj")).toBe("CNPJ");
    expect(fd.get("conta")).toBe("111");
  });

  it("usa filename de fallback laudo.<formato> sem content-disposition", async () => {
    const fn = stubFetch(new Response("bin", { status: 200 }));
    const { filename } = await fiscalLaudo({ empresaCnpj: "C", arquivos: [ofx], formato: "pdf" });
    expect(filename).toBe("laudo.pdf");
    // sem opts.conta → não acrescenta o campo
    expect((fn.mock.calls[0][1]?.body as FormData).get("conta")).toBeNull();
  });

  it("refresh-on-401: renova token e refaz a request", async () => {
    setToken("velho");
    const fn = stubFetch(
      new Response("", { status: 401 }),
      jsonOk({ access_token: "novo" }),
      new Response("bin", { status: 200 }),
    );
    const { blob } = await fiscalLaudo({ empresaCnpj: "C", arquivos: [ofx], formato: "html" });
    // Blob vem de response.blob() (undici/Node), realm diferente do Blob do jsdom
    // no CI Node 22 — toBeInstanceOf(Blob) falha. Checagem cross-realm via tag.
    expect(Object.prototype.toString.call(blob)).toBe("[object Blob]");
    expect(getToken()).toBe("novo");
    expect(fn).toHaveBeenCalledTimes(3);
    expect((fn.mock.calls[2][1]?.headers as Headers).get("Authorization")).toBe("Bearer novo");
  });

  it("401 sem refresh: limpa token, dispara logout e lança ApiError", async () => {
    setToken("velho");
    stubFetch(new Response("", { status: 401 }), new Response("", { status: 401 }));
    const ouvinte = vi.fn();
    window.addEventListener("orgconc:logout", ouvinte);
    await expect(
      fiscalLaudo({ empresaCnpj: "C", arquivos: [ofx], formato: "xlsx" }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBeNull();
    expect(ouvinte).toHaveBeenCalledTimes(1);
    window.removeEventListener("orgconc:logout", ouvinte);
  });

  it("lança ApiError em resposta !ok com detail", async () => {
    stubFetch(jsonOk({ detail: "cnpj invalido" }, { status: 422 }));
    await expect(
      fiscalLaudo({ empresaCnpj: "C", arquivos: [ofx], formato: "xlsx" }),
    ).rejects.toMatchObject({ status: 422, message: "cnpj invalido" });
  });
});

// ── métricas / dashboard / audit / activity / ai ─────────────────────────────

describe("métricas e feeds", () => {
  it("fetchDashboardBundle usa periodo default 30", async () => {
    const fn = stubFetch(jsonOk({ kpis: {}, trend: [], distribuicao: [], heatmap: [] }));
    await fetchDashboardBundle();
    expect(callAt(fn)[0]).toBe("/metrics/dashboard-bundle?periodo=30");
  });

  it("fetchDashboardBundle aceita periodo custom", async () => {
    const fn = stubFetch(jsonOk({}));
    await fetchDashboardBundle(7);
    expect(callAt(fn)[0]).toBe("/metrics/dashboard-bundle?periodo=7");
  });

  it("fetchTrustScore default 30", async () => {
    const fn = stubFetch(jsonOk({ score: 90 }));
    const out = await fetchTrustScore();
    expect(callAt(fn)[0]).toBe("/metrics/trust-score?periodo=30");
    expect(out.score).toBe(90);
  });

  it("fetchAuditTimeline default limit 10", async () => {
    const fn = stubFetch(jsonOk({ total: 0, eventos: [] }));
    await fetchAuditTimeline();
    expect(callAt(fn)[0]).toBe("/audit/timeline?limit=10");
  });

  it("fetchAuditEvento usa o id na rota", async () => {
    const fn = stubFetch(jsonOk({ id: "ev1" }));
    await fetchAuditEvento("ev1");
    expect(callAt(fn)[0]).toBe("/audit/eventos/ev1");
  });

  it("fetchActivityFeed com limit custom", async () => {
    const fn = stubFetch(jsonOk([]));
    await fetchActivityFeed(5);
    expect(callAt(fn)[0]).toBe("/activity/feed?limit=5");
  });

  it("fetchAiInsights default periodo=30 refresh=false", async () => {
    const fn = stubFetch(jsonOk({ insights: [], from_cache: false }));
    await fetchAiInsights();
    expect(callAt(fn)[0]).toBe("/ai/insights/dashboard?periodo=30&refresh=false");
  });

  it("fetchAiInsights com refresh=true", async () => {
    const fn = stubFetch(jsonOk({ insights: [] }));
    await fetchAiInsights(15, true);
    expect(callAt(fn)[0]).toBe("/ai/insights/dashboard?periodo=15&refresh=true");
  });
});

// ── admin orgs / usuários ────────────────────────────────────────────────────

describe("admin orgs e usuários", () => {
  it("listarOrgs faz GET /auth/orgs", async () => {
    const fn = stubFetch(jsonOk([]));
    await listarOrgs();
    expect(callAt(fn)[0]).toBe("/auth/orgs");
  });

  it("criarOrg faz POST /auth/orgs com JSON", async () => {
    const fn = stubFetch(jsonOk({ id: "o1", nome: "Org", plano: "free" }));
    await criarOrg({ nome: "Org" });
    const [url, init] = callAt(fn);
    expect(url).toBe("/auth/orgs");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ nome: "Org" });
  });

  it("listarUsuarios codifica o org_id na query", async () => {
    const fn = stubFetch(jsonOk([]));
    await listarUsuarios("org/com espaço");
    expect(callAt(fn)[0]).toBe("/auth/usuarios?org_id=org%2Fcom%20espa%C3%A7o");
  });

  it("criarUsuario faz POST /auth/usuarios com JSON", async () => {
    const fn = stubFetch(jsonOk({ id: "u1", email: "x@y.com", org_id: "o1", role: "user" }));
    await criarUsuario({ email: "x@y.com", senha: "s", org_id: "o1" });
    const [url, init] = callAt(fn);
    expect(url).toBe("/auth/usuarios");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toMatchObject({ email: "x@y.com", org_id: "o1" });
  });

  it("resetarSenhaUsuario faz POST /auth/usuarios/:id/senha", async () => {
    const fn = stubFetch(jsonOk({ detail: "ok" }));
    const out = await resetarSenhaUsuario("u1", "novaSenha");
    const [url, init] = callAt(fn);
    expect(url).toBe("/auth/usuarios/u1/senha");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ senha_nova: "novaSenha" });
    expect(out.detail).toBe("ok");
  });
});
