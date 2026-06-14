// Rotas de NEGÓCIO e de AUTH usam o prefixo versionado /v1 (dual-mount do
// backend). DUAS exceções ficam na raiz de propósito: /auth/refresh e
// /auth/logout — são os únicos endpoints que LEEM o cookie httpOnly de
// refresh, emitido com path fixo "/auth" (escopo mínimo); sob /v1 o browser
// não o enviaria e a rotação de sessão quebraria silenciosamente.
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
    // Raiz de propósito: lê o cookie de refresh (path "/auth") p/ revogá-lo.
    await fetch("/auth/logout", {
      method: "POST",
      credentials: "include",
    });
  } finally {
    setToken(null);
    limparDadosTenant();
  }
}

/**
 * Renova o access token via cookie de refresh httpOnly (POST /auth/refresh).
 * Retorna o novo access token, ou null se não foi possível renovar.
 *
 * Mutex: o backend rotaciona o refresh token (single-use + reuse-detection);
 * N requests com 401 simultâneo compartilham UMA chamada — sem o mutex, a 2ª
 * apresentaria o cookie já rotacionado e derrubaria a sessão inteira.
 */
let _refreshing: Promise<string | null> | null = null;

export async function apiRefresh(): Promise<string | null> {
  if (_refreshing) return _refreshing;
  _refreshing = (async () => {
    try {
      // Raiz de propósito: único endpoint que o cookie de refresh alcança.
      const res = await fetch("/auth/refresh", { method: "POST", credentials: "include" });
      if (!res.ok) return null;
      const data = (await res.json()) as { access_token?: string };
      if (data.access_token) {
        setToken(data.access_token);
        return data.access_token;
      }
      return null;
    } catch {
      return null;
    } finally {
      _refreshing = null;
    }
  })();
  return _refreshing;
}

export interface HealthResponse {
  status: string;
  versao?: string;
  api_key_configured?: boolean;
  banco_dados: string;
}

// Endpoint publico: usa fetch simples (sem auth/sem efeito de logout do apiFetch).
export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch("/v1/health", { credentials: "include" });
  return res.json();
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
  _opts: { retryOn401?: boolean } = { retryOn401: true },
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (res.status === 401) {
    // Tenta renovar o access token via refresh cookie (uma vez) antes de deslogar.
    // retryOn401=false na re-tentativa evita loop quando /auth/refresh dá 401.
    if (_opts.retryOn401 && path !== "/auth/refresh") {
      const novo = await apiRefresh();
      if (novo) return apiFetch<T>(path, init, { retryOn401: false });
    }
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

/**
 * Variante de apiFetch para respostas binárias (ex.: XLSX/PDF). Mesma lógica de
 * auth + refresh-on-401, mas devolve o Blob e o filename do Content-Disposition.
 */
export async function apiFetchBlob(
  path: string,
  init: RequestInit = {},
  _opts: { retryOn401?: boolean } = { retryOn401: true },
): Promise<{ blob: Blob; filename: string | null }> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (res.status === 401) {
    if (_opts.retryOn401 && path !== "/auth/refresh") {
      const novo = await apiRefresh();
      if (novo) return apiFetchBlob(path, init, { retryOn401: false });
    }
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
  const cd = res.headers.get("content-disposition") || "";
  // (?!\*) evita casar o `filename*=UTF-8''...` (RFC 5987) e capturar lixo.
  const m = /filename=(?!\*)"?([^";]+)"?/.exec(cd);
  return { blob: await res.blob(), filename: m ? m[1] : null };
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
  return apiFetch<LoginResponse>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, senha }),
  });
}

export async function fetchMe() {
  return apiFetch<UserMe>("/v1/auth/me");
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
  return apiFetch<ConciliacaoResponse>(`/v1/conciliar/ofx${q}`, { method: "POST", body: fd });
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

let _clientesCache: unknown[] | null = null;
let _clientesCacheAt = 0;
const CLIENTES_TTL_MS = 60_000;

export async function listarClientes() {
  if (_clientesCache !== null && (performance.now() - _clientesCacheAt) < CLIENTES_TTL_MS) {
    return _clientesCache as Cliente[];
  }
  const result = await apiFetch<Cliente[]>("/v1/clientes");
  _clientesCache = result;
  _clientesCacheAt = performance.now();
  return result;
}

export function invalidarCacheClientes(): void { _clientesCache = null; _clientesCacheAt = 0; }

/**
 * Limpa todo dado tenant-scoped do browser: cache em memória (clientes) + chaves
 * `orgconc.*` em session/localStorage (histórico, último resultado, token).
 * Chamado no logout explícito e na expiração de sessão para impedir que o próximo
 * usuário no mesmo browser veja dados da organização anterior.
 */
export function limparDadosTenant(): void {
  invalidarCacheClientes();
  try {
    for (const storage of [window.sessionStorage, window.localStorage]) {
      const remover: string[] = [];
      for (let i = 0; i < storage.length; i++) {
        const k = storage.key(i);
        if (k && k.startsWith("orgconc.")) remover.push(k);
      }
      remover.forEach((k) => storage.removeItem(k));
    }
  } catch {
    /* storage indisponível (modo privado) — ignore */
  }
}

export async function criarCliente(data: Partial<Cliente>) {
  return apiFetch<Cliente>("/v1/clientes", { method: "POST", body: JSON.stringify(data) });
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
  return apiFetch<ConciliacaoMeta[]>(`/v1/conciliacoes${q}`);
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
  return apiFetch<Cliente>(`/v1/clientes/${id}`, { method: "PATCH", body: JSON.stringify(data) });
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
  return apiFetch<ConciliacaoResponse>(`/v1/conciliar/csv${q}`, { method: "POST", body: fd });
}

export async function listarConciliacoesDoCliente(clienteId: string) {
  return apiFetch<ConciliacaoMeta[]>(`/v1/conciliacoes/por-cliente/${clienteId}`);
}

// ── Matchers (OrgNeural2) ─────────────────────────────────────────────────

export interface DisposicaoItem {
  data: string;
  tipo: string;
  valor: number;
  fitid: string;
  memo: string;
  nome: string;
  estagio: number;
  disposicao: string;
  contraparte: string | null;
  conta_contabil: string | null;
  origem: string | null;
  flag: string | null;
  nfe_chave: string | null;
}

export interface MatchersResponse {
  cliente_id: string;
  total_transacoes: number;
  automatizadas: number;
  taxa_automatizacao_pct: number;
  disposicoes: DisposicaoItem[];
  xmls_indexados: number;
}

export async function conciliarMatchers(
  clienteId: string,
  arquivos: File[],
): Promise<MatchersResponse> {
  const fd = new FormData();
  fd.append("cliente_id", clienteId);
  arquivos.forEach((f) => fd.append("arquivos", f));
  return apiFetch<MatchersResponse>("/v1/matchers/conciliar", { method: "POST", body: fd });
}

// ── Guias tributárias ─────────────────────────────────────────────────────

export interface Guia {
  id: string;
  cliente_id: string;
  tipo: string;
  codigo_receita: string | null;
  valor: number;
  competencia: string | null;
  data_vencimento: string | null;
  conta_contabil: string | null;
  ativo: boolean;
  criado_em: string;
}

export async function listarGuias(clienteId?: string): Promise<Guia[]> {
  const q = clienteId ? `?cliente_id=${clienteId}` : "";
  return apiFetch<Guia[]>(`/v1/guias${q}`);
}

export async function criarGuia(data: {
  cliente_id: string;
  tipo: string;
  valor: number;
  codigo_receita?: string | null;
  competencia?: string | null;
  data_vencimento?: string | null;
  conta_contabil?: string | null;
}): Promise<Guia> {
  return apiFetch<Guia>("/v1/guias", { method: "POST", body: JSON.stringify(data) });
}

// ── Contratos recorrentes ─────────────────────────────────────────────────

export interface Contrato {
  id: string;
  cliente_id: string;
  descricao: string;
  valor: number;
  periodicidade: string | null;
  padrao_memo: string | null;
  conta_contabil: string | null;
  ativo: boolean;
  criado_em: string;
}

export async function listarContratos(clienteId?: string): Promise<Contrato[]> {
  const q = clienteId ? `?cliente_id=${clienteId}` : "";
  return apiFetch<Contrato[]>(`/v1/contratos${q}`);
}

export async function criarContrato(data: {
  cliente_id: string;
  descricao: string;
  valor: number;
  periodicidade?: string;
  padrao_memo?: string | null;
  conta_contabil?: string | null;
}): Promise<Contrato> {
  return apiFetch<Contrato>("/v1/contratos", { method: "POST", body: JSON.stringify(data) });
}

// ── Fiscal (Auditoria Cruzada NF-e/CT-e × OFX) ────────────────────────────

export interface FiscalProcessarResponse {
  cliente_id: string;
  documentos_processados: number;
  documentos_por_tipo: Record<string, number>;
  ofx_transacoes: number;
  cruzamentos: {
    total: number;
    por_status: Record<string, number>;
    volume_por_status: Record<string, number>;
  } | null;
  fornecedores_classificados: number;
}

export interface FiscalFornecedor {
  cnpj: string;
  razao_social: string;
  volume_pago: number;
  volume_nf: number;
  conformidade_pct: number;
  n_pagamentos: number;
  n_nfes: number;
  risco_classe: "BAIXO" | "MEDIO" | "ALTO" | "CRITICO";
  risco_tributario_anual: number;
  flags: string[];
  periodo_inicio: string | null;
  periodo_fim: string | null;
}

export interface FiscalConformidadeResponse {
  cliente_id: string;
  total: number;
  fornecedores: FiscalFornecedor[];
}

export interface FiscalRiscoResponse {
  cliente_id: string;
  risco_total_anual: number;
  risco_despesa_indedutivel_anual: number;
  risco_retencoes_anual: number;
  por_classe_risco: Record<string, number>;
  por_flag: Record<string, number>;
  contagem_fornecedores: Record<string, number>;
  total_fornecedores: number;
  top_10_fornecedores: Array<{
    cnpj: string;
    razao_social: string;
    risco_anual: number;
    classe: string;
    flags: string[];
  }>;
  retencoes: {
    base_pj_anual: number;
    retencao_pj_anual: number;
    total_anual: number;
    aliquotas: Record<string, number>;
  };
  regime_pressuposto: string;
  aliquota_aplicada_pct: number;
}

export async function fiscalProcessar(
  clienteId: string,
  arquivos: File[],
  enrichAll = false,
): Promise<FiscalProcessarResponse> {
  const fd = new FormData();
  fd.append("cliente_id", clienteId);
  arquivos.forEach((f) => fd.append("arquivos", f));
  if (enrichAll) fd.append("enrich_all", "true");
  return apiFetch<FiscalProcessarResponse>("/v1/fiscal/processar", {
    method: "POST",
    body: fd,
  });
}

export type FormatoLaudo = "xlsx" | "html" | "pdf";

/**
 * Gera o Laudo Integrado (POST /fiscal/laudo) e devolve o arquivo como Blob.
 * Aceita OFX + (opcional) XMLs/ZIPs de NF-e/CT-e — com XMLs o laudo ganha as
 * abas/seções fiscais. Faz refresh do token uma vez em 401 (igual ao apiFetch).
 */
export async function fiscalLaudo(opts: {
  empresaCnpj: string;
  conta?: string;
  arquivos: File[];
  formato: FormatoLaudo;
}): Promise<{ blob: Blob; filename: string }> {
  const fd = new FormData();
  fd.append("empresa_cnpj", opts.empresaCnpj);
  if (opts.conta) fd.append("conta", opts.conta);
  opts.arquivos.forEach((f) => fd.append("arquivos", f));

  const url = `/v1/fiscal/laudo?formato=${opts.formato}`;
  const doFetch = (token: string | null) => {
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, { method: "POST", body: fd, headers, credentials: "include" });
  };

  let res = await doFetch(getToken());
  if (res.status === 401) {
    const novo = await apiRefresh();
    if (novo) {
      res = await doFetch(novo);
    } else {
      setToken(null);
      window.dispatchEvent(new Event("orgconc:logout"));
      throw new ApiError("Sessão expirada", 401);
    }
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
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  const filename = m ? m[1] : `laudo.${opts.formato}`;
  return { blob, filename };
}

/**
 * Baixa um export autenticado (/export/*) com Bearer e dispara o download.
 * Substitui os antigos <a href> diretos: navegação de link não envia o
 * Authorization header (401), e abrir o HTML do backend em _blank no mesmo
 * origin ampliaria a superfície de XSS — baixar o arquivo resolve os dois.
 */
export async function baixarExport(path: string, fallbackFilename: string): Promise<void> {
  const { blob, filename } = await apiFetchBlob(path);
  baixarBlob(blob, filename || fallbackFilename);
}

/** Dispara o download de um Blob no browser. */
export function baixarBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function fiscalConformidade(
  clienteId: string,
  classeMinima?: string,
): Promise<FiscalConformidadeResponse> {
  const q = classeMinima ? `?classe_minima=${classeMinima}` : "";
  return apiFetch<FiscalConformidadeResponse>(
    `/v1/fiscal/conformidade/${clienteId}${q}`,
  );
}

export async function fiscalRiscoTributario(
  clienteId: string,
): Promise<FiscalRiscoResponse> {
  return apiFetch<FiscalRiscoResponse>(`/v1/fiscal/risco-tributario/${clienteId}`);
}

export interface FiscalCartaResponse {
  cliente_id: string;
  cliente_nome: string;
  versao: string;
  risco_total: number;
  total_fornecedores: number;
  payload_hash: string;
  markdown: string;
  pdf_base64: string | null;
}

export interface FiscalCartaItem {
  id: string;
  versao: string;
  risco_total: number;
  total_fornecedores: number;
  payload_hash: string;
  gerado_em: string | null;
}

export interface FiscalCartasResponse {
  cliente_id: string;
  total: number;
  cartas: FiscalCartaItem[];
}

export async function fiscalGerarCarta(
  clienteId: string,
): Promise<FiscalCartaResponse> {
  return apiFetch<FiscalCartaResponse>(`/v1/fiscal/gerar-carta/${clienteId}`, {
    method: "POST",
  });
}

export async function fiscalListarCartas(
  clienteId: string,
): Promise<FiscalCartasResponse> {
  return apiFetch<FiscalCartasResponse>(`/v1/fiscal/cartas/${clienteId}`);
}

// ── Auditoria Forense (regime×teto + heatmap + sinais) ─────────────────────
// Espelha o motor PRINCIPAL (laudo_forense): upload OFX → resumo JSON, e o XLSX
// de 11 abas via /fiscal/laudo. Stateless/cache-only (sem persistir por cliente).

export type RegimeClasse = "COMPATIVEL" | "ATENCAO" | "ALTO" | "CRITICO";
export type RiscoClasse = "BAIXO" | "MEDIO" | "ALTO" | "CRITICO";

export interface FiscalAuditoriaRegime {
  volume_bruto: number;
  volume_anualizado: number;
  teto: number;
  multiplo_do_teto: number;
  classe: RegimeClasse;
  incompativel: boolean;
}

export interface FiscalAuditoriaDisposicao {
  data: string;
  valor: number;
  cnpj: string;
  meio: string;
  categoria_tributaria: string;
  risk_score: number;
  risco_classe: RiscoClasse;
  sinais: string[];
}

export interface FiscalAuditoriaResumo {
  empresa: {
    cnpj: string;
    razao_social: string;
    porte: string;
    situacao: string;
    cnae: string;
  };
  conta: string | null;
  periodo: { inicio: string | null; fim: string | null };
  /** CNPJs ainda não enriquecidos; >0 → pós-baixa pode estar incompleta (enriquecimento em background). */
  enriquecimento_pendente: number;
  regime: FiscalAuditoriaRegime;
  n_transacoes: number;
  meses_observados: number;
  heatmap: Record<string, { qtd: number; volume: number }>;
  retencao_estimada: number;
  sinais: { pos_baixa: number; smurfing: number; carrossel: number };
  top_disposicoes: FiscalAuditoriaDisposicao[];
}

export async function fiscalLaudoResumo(
  empresaCnpj: string,
  conta: string,
  arquivos: File[],
): Promise<FiscalAuditoriaResumo> {
  const fd = new FormData();
  fd.append("empresa_cnpj", empresaCnpj);
  fd.append("conta", conta);
  arquivos.forEach((f) => fd.append("arquivos", f));
  return apiFetch<FiscalAuditoriaResumo>("/v1/fiscal/laudo/resumo", {
    method: "POST",
    body: fd,
  });
}

export async function fiscalLaudoBlob(
  empresaCnpj: string,
  conta: string,
  arquivos: File[],
): Promise<{ blob: Blob; filename: string | null }> {
  const fd = new FormData();
  fd.append("empresa_cnpj", empresaCnpj);
  fd.append("conta", conta);
  arquivos.forEach((f) => fd.append("arquivos", f));
  return apiFetchBlob("/v1/fiscal/laudo", { method: "POST", body: fd });
}

// ── Fila de jobs assíncronos (P1 #9, backend #122) ───────────────────────────

export type JobStatusNome = "PENDENTE" | "EXECUTANDO" | "CONCLUIDO" | "ERRO";

export interface JobStatus {
  id: string;
  tipo: string;
  status: JobStatusNome;
  erro: string | null;
  tentativas: number;
  criado_em: string | null;
  iniciado_em: string | null;
  concluido_em: string | null;
  resultado_nome: string | null;
  resultado_mime: string | null;
}

export interface JobSubmetido {
  job_id: string;
  status: JobStatusNome;
  polling: string;
  resultado: string;
}

export async function fiscalLaudoAsync(opts: {
  empresaCnpj: string;
  conta?: string;
  arquivos: File[];
  formato: FormatoLaudo;
}): Promise<JobSubmetido> {
  const fd = new FormData();
  fd.append("empresa_cnpj", opts.empresaCnpj);
  if (opts.conta) fd.append("conta", opts.conta);
  opts.arquivos.forEach((f) => fd.append("arquivos", f));
  return apiFetch<JobSubmetido>(`/v1/fiscal/laudo/async?formato=${opts.formato}`, {
    method: "POST",
    body: fd,
  });
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  return apiFetch<JobStatus>(`/v1/jobs/${jobId}`);
}

export async function baixarJobResultado(
  jobId: string,
): Promise<{ blob: Blob; filename: string | null }> {
  return apiFetchBlob(`/v1/jobs/${jobId}/resultado`);
}

/** Fase corrente do laudo via fila, para feedback de UI. */
export type FaseLaudo = JobStatusNome | "SINCRONO";

/**
 * Gera o laudo pela FILA (não bloqueia o backend): submete, faz polling e baixa
 * o resultado. Se a fila não estiver disponível — 503 (sem banco) ou 403 (token
 * sem organização, ex.: service token) — cai no fluxo síncrono transparente.
 * `onFase` recebe PENDENTE/EXECUTANDO/CONCLUIDO ou SINCRONO (fallback).
 */
export async function gerarLaudoComFila(
  opts: { empresaCnpj: string; conta?: string; arquivos: File[]; formato: FormatoLaudo },
  onFase?: (fase: FaseLaudo) => void,
  pollMs = 3000,
): Promise<{ blob: Blob; filename: string; viaFila: boolean }> {
  let sub: JobSubmetido;
  try {
    sub = await fiscalLaudoAsync(opts);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 503 || err.status === 403)) {
      onFase?.("SINCRONO");
      const { blob, filename } = await fiscalLaudo(opts);
      return { blob, filename, viaFila: false };
    }
    throw err;
  }
  onFase?.(sub.status);
  const limite = Date.now() + 10 * 60_000; // jobs têm timeout no servidor (15min)
  while (Date.now() < limite) {
    await new Promise((r) => setTimeout(r, pollMs));
    const st = await fetchJobStatus(sub.job_id);
    onFase?.(st.status);
    if (st.status === "CONCLUIDO") {
      const { blob, filename } = await baixarJobResultado(sub.job_id);
      return {
        blob,
        filename: filename ?? st.resultado_nome ?? `laudo.${opts.formato}`,
        viaFila: true,
      };
    }
    if (st.status === "ERRO") {
      throw new ApiError(st.erro || "Falha ao gerar o laudo (job)", 422);
    }
  }
  throw new ApiError("Tempo esgotado aguardando o laudo na fila", 408);
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

export async function fetchDashboardBundle(periodo = 30) {
  return apiFetch<DashboardBundle>(`/v1/metrics/dashboard-bundle?periodo=${periodo}`);
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
  return apiFetch<TrustScore>(`/v1/metrics/trust-score?periodo=${periodo}`);
}

export async function fetchAuditTimeline(limit = 10) {
  return apiFetch<AuditTimelineResponse>(`/v1/audit/timeline?limit=${limit}`);
}

export async function fetchAuditEvento(eventoId: string) {
  return apiFetch<AuditEventDetalhe>(`/v1/audit/eventos/${eventoId}`);
}

// ── PR 5: AI insights, performance modelos, activity feed ────────────────

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

export async function fetchActivityFeed(limit = 10) {
  return apiFetch<ActivityFeedItem[]>(`/v1/activity/feed?limit=${limit}`);
}

export async function fetchAiInsights(periodo = 30, refresh = false) {
  return apiFetch<AiInsightsResponse>(
    `/v1/ai/insights/dashboard?periodo=${periodo}&refresh=${refresh}`
  );
}

// ── Administração de organizações e usuários (admin/service) ──────────────

export interface OrgAdmin {
  id: string;
  nome: string;
  cnpj: string | null;
  plano: string;
  ativo: boolean;
  criado_em: string | null;
}

export interface UsuarioAdmin {
  id: string;
  email: string;
  nome: string | null;
  role: string;
  ativo: boolean;
  criado_em: string | null;
}

export async function listarOrgs(): Promise<OrgAdmin[]> {
  return apiFetch<OrgAdmin[]>("/v1/auth/orgs");
}

export async function criarOrg(data: {
  nome: string;
  cnpj?: string;
  plano?: string;
}): Promise<{ id: string; nome: string; plano: string }> {
  return apiFetch("/v1/auth/orgs", { method: "POST", body: JSON.stringify(data) });
}

export async function listarUsuarios(orgId: string): Promise<UsuarioAdmin[]> {
  return apiFetch<UsuarioAdmin[]>(`/v1/auth/usuarios?org_id=${encodeURIComponent(orgId)}`);
}

export async function criarUsuario(data: {
  email: string;
  senha: string;
  org_id: string;
  role?: string;
  nome?: string;
}): Promise<{ id: string; email: string; org_id: string; role: string }> {
  return apiFetch("/v1/auth/usuarios", { method: "POST", body: JSON.stringify(data) });
}

export async function resetarSenhaUsuario(
  usuarioId: string,
  senhaNova: string,
): Promise<{ detail: string }> {
  return apiFetch(`/v1/auth/usuarios/${usuarioId}/senha`, {
    method: "POST",
    body: JSON.stringify({ senha_nova: senhaNova }),
  });
}
