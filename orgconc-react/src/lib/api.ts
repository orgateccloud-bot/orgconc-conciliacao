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

export async function apiLogout(): Promise<void> {
  try {
    await fetch("/auth/logout", {
      method: "POST",
      credentials: "include",
    });
  } finally {
    setToken(null);
  }
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
  const res = await fetch(path, { ...init, headers, credentials: "include" });
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

// ── Dashboard metrics (PR 1 backend) ──────────────────────────────────────

export interface KpisDelta {
  conciliacoes_pct: number | null;
  transacoes_pct: number | null;
  anomalias_pct: number | null;
}

export interface KpisBlock {
  periodo_dias: number;
  conciliacoes: number;
  transacoes: number;
  anomalias: number;
  volume_total: number;
  taxa_anomalias_pct: number;
  delta: KpisDelta;
}

export interface TrendPoint {
  data: string;          // YYYY-MM-DD
  conciliacoes: number;
  transacoes: number;
  anomalias: number;
}

export interface DistribuicaoItem {
  modo: string;
  qtd: number;
}

export interface HeatmapDay {
  data: string;          // YYYY-MM-DD
  valor: number;
}

export interface DashboardBundle {
  kpis: KpisBlock;
  trend: TrendPoint[];
  distribuicao: DistribuicaoItem[];
  heatmap: HeatmapDay[];
  gerado_em: number;
  cache_ttl_s: number;
}

export interface TransacaoRecente {
  id: string;
  conciliacao_id: string | null;
  data_lancamento: string | null;
  valor: number | null;
  memo: string | null;
  categoria: string | null;
  banco: string | null;
  tipo: string | null;
  eh_anomalia: boolean;
  criado_em: string | null;
}

export async function fetchDashboardBundle(periodo = 30) {
  return apiFetch<DashboardBundle>(`/metrics/dashboard-bundle?periodo=${periodo}`);
}

export async function fetchTransacoesRecentes(limit = 10) {
  return apiFetch<TransacaoRecente[]>(`/transacoes/recentes?limit=${limit}`);
}

// ── Trust score + audit (PR 4 backend) ────────────────────────────────────

export interface TrustScore {
  score: number;
  periodo_dias: number;
  breakdown: {
    taxa_sucesso_pct: number;
    dias_sem_falha: number;
    cobertura_pct: number;
  };
  metricas: {
    total_conciliacoes: number;
    conciliacoes_limpas: number;
    total_transacoes: number;
    total_anomalias: number;
    taxa_anomalias_pct: number;
  };
  descricao: string;
}

export interface AuditEventSummary {
  id: string;
  ts: string | null;
  actor_email: string | null;
  actor_sub: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  payload_hash: string;
  prev_hash: string;
  payload_hash_short: string | null;
  request_id: string | null;
}

export interface AuditEventDetalhe extends AuditEventSummary {
  payload: Record<string, unknown> | null;
  payload_hash_valid: boolean;
}

export interface AuditTimelineResponse {
  total: number;
  limit: number;
  offset: number;
  cadeia_integra: boolean;
  cadeia_motivo: string | null;
  eventos: AuditEventSummary[];
}

export async function fetchTrustScore(periodo = 30) {
  return apiFetch<TrustScore>(`/metrics/trust-score?periodo=${periodo}`);
}

export async function fetchAuditTimeline(limit = 10) {
  return apiFetch<AuditTimelineResponse>(`/audit/timeline?limit=${limit}`);
}

export async function fetchAuditEvento(eventoId: string) {
  return apiFetch<AuditEventDetalhe>(`/audit/eventos/${eventoId}`);
}

// ── PR 5: AI insights, performance modelos, activity feed ────────────────

export interface ModeloPerf {
  modo: string;
  qtd: number;
  latency_ms_avg: number | null;
  transacoes: number;
  anomalias: number;
}

export interface ActivityFeedItem {
  id: string;
  ts: string | null;
  titulo: string;
  severidade: "info" | "success" | "warn";
  ator: string;
  resource_id: string | null;
}

export interface AiInsight {
  tipo: "info" | "success" | "warn";
  titulo: string;
  texto: string;
  cta: string | null;
}

export interface AiInsightsResponse {
  insights: AiInsight[];
  from_cache: boolean;
  gerado_em: string;
  expira_em: string;
}

export async function fetchPerformanceModelos(periodo = 30) {
  return apiFetch<ModeloPerf[]>(`/metrics/modelos?periodo=${periodo}`);
}

export async function fetchActivityFeed(limit = 10) {
  return apiFetch<ActivityFeedItem[]>(`/activity/feed?limit=${limit}`);
}

export async function fetchAiInsights(periodo = 30, refresh = false) {
  return apiFetch<AiInsightsResponse>(
    `/ai/insights/dashboard?periodo=${periodo}&refresh=${refresh}`
  );
}
