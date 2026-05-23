const TOKEN_KEY = "orgconc.access_token";

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
  ) {
    super(message);
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event("orgconc:logout"));
    throw new ApiError("Sessão expirada", 401);
  }
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    const msg =
      typeof detail === "object" && detail && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Erro ${res.status}`;
    throw new ApiError(msg, res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json() as Promise<T>;
  return res.text() as Promise<T>;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface UserMe {
  sub: string;
  email?: string;
  role: string;
}

export interface Anomalia {
  severidade: string;
  tipo: string;
  titulo: string;
  conta: string;
  valor: number;
  detalhe: string;
}

export interface ConciliacaoResponse {
  modo: string;
  report_id: string;
  extratos: { arquivo: string; conta: string; qtd: number }[];
  anomalias: Anomalia[];
  relatorio_md: string;
  relatorio_html?: string;
  persistencia?: { status: string };
  usage?: { input_tokens: number; output_tokens: number };
  score_consenso?: number;
}

export async function login(email: string, senha: string) {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, senha }),
  });
}

export async function fetchMe() {
  return apiFetch<UserMe>("/auth/me");
}

export async function conciliarOfx(
  files: File[],
  opts: { simular?: boolean; multi_modelo?: boolean; modelo?: string },
) {
  const fd = new FormData();
  files.forEach((f) => fd.append("arquivos", f));
  const params = new URLSearchParams();
  if (opts.simular) params.set("simular", "true");
  else if (opts.multi_modelo) params.set("multi_modelo", "true");
  else if (opts.modelo) params.set("modelo", opts.modelo);
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<ConciliacaoResponse>(`/conciliar/ofx${q}`, { method: "POST", body: fd });
}

export interface Cliente {
  id: string;
  nome: string;
  cnpj?: string;
  email?: string;
  telefone?: string;
  plano: string;
  ativo?: boolean;
}

export async function listarClientes() {
  return apiFetch<Cliente[]>("/clientes");
}

export async function criarCliente(data: Partial<Cliente>) {
  return apiFetch<Cliente>("/clientes", { method: "POST", body: JSON.stringify(data) });
}

export async function consultarCnpjSerpro(cnpj: string) {
  return apiFetch<{ tipo: string; documento_mascarado: string; dados: Record<string, unknown> }>(
    "/serpro/cnpj",
    { method: "POST", body: JSON.stringify({ cnpj }) },
  );
}

export interface ConciliacaoMeta {
  report_id: string;
  modo: string;
  total_transacoes: number;
  total_anomalias: number;
  criado_em: string;
  exports: { html: string; xlsx: string; pdf: string };
}

export async function listarConciliacoes(clienteId?: string) {
  const params = new URLSearchParams();
  if (clienteId) params.set("cliente_id", clienteId);
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<ConciliacaoMeta[]>(`/conciliacoes${q}`);
}

const HIST_KEY = "orgconc.historico.v1";

export function salvarHistoricoLocal(entry: {
  id: string;
  modo: string;
  ts: string;
  total_tx: number;
  total_anom: number;
}) {
  try {
    const raw = localStorage.getItem(HIST_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    arr.push(entry);
    localStorage.setItem(HIST_KEY, JSON.stringify(arr.slice(-30)));
  } catch {
    /* ignore */
  }
}

export function carregarHistoricoLocal() {
  try {
    const raw = localStorage.getItem(HIST_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export async function atualizarCliente(id: string, data: Partial<Cliente>) {
  return apiFetch<Cliente>(`/clientes/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function conciliarCsv(
  files: File[],
  opts: { simular?: boolean; multi_modelo?: boolean; modelo?: string },
) {
  const fd = new FormData();
  files.forEach((f) => fd.append("arquivos", f));
  const params = new URLSearchParams();
  if (opts.simular) params.set("simular", "true");
  else if (opts.multi_modelo) params.set("multi_modelo", "true");
  else if (opts.modelo) params.set("modelo", opts.modelo);
  const q = params.toString() ? `?${params}` : "";
  return apiFetch<ConciliacaoResponse>(`/conciliar/csv${q}`, { method: "POST", body: fd });
}

export async function listarConciliacoesDoCliente(clienteId: string) {
  return apiFetch<ConciliacaoMeta[]>(`/conciliacoes/por-cliente/${clienteId}`);
}

export async function consultarCpfSerpro(cpf: string) {
  return apiFetch<{ tipo: string; documento_mascarado: string; dados: Record<string, unknown> }>(
    "/serpro/cpf",
    { method: "POST", body: JSON.stringify({ cpf }) },
  );
}
