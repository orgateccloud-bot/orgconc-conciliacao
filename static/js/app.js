/* OrgConc Dashboard v0.4.0 — extraido de frontend/index.html */
/* ── Estado ──────────────────────────────────────────────────────── */
const API = '';  // mesmo origin
const STORAGE_KEY = 'orgconc.historico.v1';
const THEME_KEY   = 'orgconc.tema.v1';
const MAX_HIST    = 30;

let _modo = 'llm';
let _arquivos = [];
let _reportId = null;
let _historicoRelatorios = carregarHistorico();
let _chartCategorias   = null;
let _chartAnomalias    = null;
let _chartFluxo        = null;
let _chartContrapartes = null;
let _chartRadar        = null;
let _chartSemana       = null;
let _ultimoDataset     = null;

/* ── Persistencia local (localStorage) ──────────────────────────── */
function carregarHistorico() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.map(r => ({ ...r, ts: new Date(r.ts) })) : [];
  } catch { return []; }
}

function persistirHistorico() {
  try {
    const slim = _historicoRelatorios.slice(-MAX_HIST).map(r => ({
      id: r.id, modo: r.modo, modelo_label: r.modelo_label,
      ts: r.ts instanceof Date ? r.ts.toISOString() : r.ts,
      total_tx: r.total_tx ?? 0, total_anom: r.total_anom ?? 0,
      score: r.score ?? null,
    }));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(slim));
  } catch (e) { console.warn('Falha ao persistir historico:', e); }
}

function limparHistorico() {
  if (!confirm('Limpar todo o histórico local de relatórios?')) return;
  _historicoRelatorios = [];
  persistirHistorico();
  atualizarHistorico();
  toast('Histórico limpo.', 'success');
}

/* ── Tema (dark/light) ──────────────────────────────────────────── */
function aplicarTema(tema) {
  document.documentElement.setAttribute('data-theme', tema);
  const btn = document.getElementById('btn-theme');
  if (btn) {
    btn.setAttribute('aria-label', tema === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro');
    btn.dataset.tema = tema;
  }
  try { localStorage.setItem(THEME_KEY, tema); } catch {}
  // Re-renderiza charts para refletir paleta
  if (_ultimoDataset) renderizarCharts(_ultimoDataset);
}

function toggleTema() {
  const atual = document.documentElement.getAttribute('data-theme') || 'light';
  aplicarTema(atual === 'dark' ? 'light' : 'dark');
}

(function _initTema() {
  let tema;
  try { tema = localStorage.getItem(THEME_KEY); } catch {}
  if (!tema) {
    tema = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  aplicarTema(tema);
})();

/* ── Navegação ──────────────────────────────────────────────────── */
document.querySelectorAll('.nav-item[data-section]').forEach(btn => {
  btn.addEventListener('click', () => navegar(btn.dataset.section));
});

function navegar(secao) {
  document.querySelectorAll('.nav-item').forEach(b => {
    b.classList.toggle('active', b.dataset.section === secao);
    b.setAttribute('aria-current', b.dataset.section === secao ? 'page' : 'false');
  });
  document.querySelectorAll('.section').forEach(s => {
    s.classList.toggle('active', s.id === 'section-' + secao);
  });
  const titulos = { conciliacao: 'Conciliação Bancária', clientes: 'Clientes', relatorios: 'Histórico de Relatórios' };
  document.getElementById('topbar-title').textContent = titulos[secao] || secao;
  if (secao === 'clientes') carregarClientes();
}

/* ── Steps ──────────────────────────────────────────────────────── */
function atualizarSteps() {
  const temArquivos = _arquivos.length > 0;
  const s1 = document.getElementById('step-1');
  const s2 = document.getElementById('step-2');
  const s3 = document.getElementById('step-3');
  s1.className = 'step done';
  s2.className = temArquivos ? 'step done' : 'step active';
  s3.className = temArquivos ? 'step active' : 'step';
}

/* ── Modo ───────────────────────────────────────────────────────── */
function selecionarModo(el) {
  document.querySelectorAll('.mode-card').forEach(c => {
    c.classList.remove('selected');
    c.setAttribute('aria-checked', 'false');
  });
  el.classList.add('selected');
  el.setAttribute('aria-checked', 'true');
  _modo = el.dataset.mode;
  atualizarBotaoCTA();
}

function teclaCard(e, el) {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selecionarModo(el); }
}

/* ── Upload ─────────────────────────────────────────────────────── */
function dragOver(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.add('drag-over');
}
function dragLeave() {
  document.getElementById('upload-zone').classList.remove('drag-over');
}
function drop(e) {
  e.preventDefault();
  dragLeave();
  arquivosSelecionados(e.dataTransfer.files);
}
function arquivosSelecionados(fileList) {
  const aceitos = ['.ofx', '.pdf', '.xml'];
  Array.from(fileList).forEach(f => {
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!aceitos.includes(ext)) { toast(`Arquivo ignorado: ${f.name} (formato não suportado)`, 'error'); return; }
    if (_arquivos.find(a => a.name === f.name)) return;
    _arquivos.push(f);
  });
  renderFileList();
  atualizarSteps();
  atualizarBotaoCTA();
}

function renderFileList() {
  const lista = document.getElementById('file-list');
  lista.innerHTML = _arquivos.map((f, i) => `
    <div class="file-item">
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <span class="file-item-name">${esc(f.name)}</span>
      <span class="file-item-size">${formatBytes(f.size)}</span>
      <button class="file-remove" onclick="removerArquivo(${i})" aria-label="Remover ${esc(f.name)}">✕</button>
    </div>`).join('');
}

function removerArquivo(i) {
  _arquivos.splice(i, 1);
  renderFileList();
  atualizarSteps();
  atualizarBotaoCTA();
}

function atualizarBotaoCTA() {
  const btn = document.getElementById('btn-conciliar');
  const desc = document.getElementById('cta-desc');
  const temArquivos = _arquivos.length > 0;
  btn.disabled = !temArquivos;
  const nomes = {
    simulacao: 'Python Heurístico',
    haiku:     'Claude Haiku 4.5',
    llm:       'Claude Sonnet 4.6',
    multi:     'Multi-Modelo (3 modelos)',
  };
  const cores = {
    simulacao: 'btn-green',
    haiku:     'btn-primary',
    llm:       'btn-primary',
    multi:     'btn-purple',
  };
  btn.className = `btn ${cores[_modo] || 'btn-primary'} btn-lg`;
  if (temArquivos) {
    desc.textContent = `${_arquivos.length} arquivo(s) · Modo: ${nomes[_modo]}`;
  } else {
    desc.textContent = 'Selecione arquivos para continuar';
  }
}

/* ── Conciliação ────────────────────────────────────────────────── */
async function iniciarConciliacao() {
  if (!_arquivos.length) return;

  // Esconde forms, mostra loading
  document.getElementById('card-mode').classList.add('hidden');
  document.getElementById('card-upload').classList.add('hidden');
  document.getElementById('card-cta').classList.add('hidden');
  document.getElementById('result-panel').classList.remove('active');
  document.getElementById('result-panel').style.display = 'none';

  const loading = document.getElementById('loading-panel');
  loading.classList.add('active');

  // Ajusta dots para o modo
  const isMulti = _modo === 'multi';
  const isSim   = _modo === 'simulacao';
  ['dot-opus','dot-sonnet-multi','dot-haiku'].forEach(id => {
    document.getElementById(id).classList.toggle('hidden', !isMulti);
  });
  document.getElementById('dot-single').classList.toggle('hidden', isMulti);
  document.getElementById('loading-title').textContent =
    isMulti ? 'Consultando 3 modelos em paralelo…' :
    isSim   ? 'Analisando com heurísticas locais…' :
              'Analisando com Claude Sonnet 4.6…';
  document.getElementById('loading-sub').textContent =
    isMulti ? 'Opus 4.7 + Sonnet 4.6 + Haiku 4.5 gerando análises independentes' :
    isSim   ? 'Aplicando regras contábeis brasileiras' :
              'Claude está lendo e cruzando as transações';

  // Reinicia a barra de progresso
  const bar = document.getElementById('loading-bar-fill');
  bar.style.animation = 'none';
  bar.offsetHeight; // reflow
  bar.style.animation = '';

  const fd = new FormData();
  _arquivos.forEach(f => fd.append('arquivos', f));

  let url = `${API}/conciliar/ofx`;
  const params = new URLSearchParams();
  if (_modo === 'simulacao') params.set('simular', 'true');
  else if (_modo === 'multi') params.set('multi_modelo', 'true');
  else if (_modo === 'haiku') params.set('modelo', 'haiku');
  // _modo === 'llm' usa o default (modelo=sonnet)
  if (params.toString()) url += '?' + params;

  try {
    const resp = await fetch(url, { method: 'POST', body: fd });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      const msg = typeof err.detail === 'object' ? JSON.stringify(err.detail) : String(err.detail);
      throw new Error(msg);
    }
    const data = await resp.json();
    bar.style.width = '100%';
    setTimeout(() => renderResultado(data), 300);
  } catch(err) {
    loading.classList.remove('active');
    document.getElementById('card-mode').classList.remove('hidden');
    document.getElementById('card-upload').classList.remove('hidden');
    document.getElementById('card-cta').classList.remove('hidden');
    toast('Erro: ' + err.message, 'error');
  }
}

function renderResultado(data) {
  const loading = document.getElementById('loading-panel');
  loading.classList.remove('active');

  _reportId = data.report_id;
  _ultimoDataset = data;

  const totalTx_  = data.extratos?.reduce((s, e) => s + e.qtd, 0) ?? 0;
  const totalAnom_ = data.anomalias?.length ?? 0;
  _historicoRelatorios.push({
    id: _reportId,
    modo: data.modo,
    modelo_label: data.modelo_label || null,
    ts: new Date(),
    total_tx: totalTx_,
    total_anom: totalAnom_,
    score: data.score_consenso ?? null,
  });
  persistirHistorico();
  atualizarHistorico();
  renderizarCharts(data);

  // KPIs
  const totalTx  = data.extratos?.reduce((s, e) => s + e.qtd, 0) ?? 0;
  const totalAnom = data.anomalias?.length ?? 0;
  // Quando claude_llm, prefere modelo_label do backend (Haiku / Sonnet / Opus)
  const baseLabel = { simulacao_local: 'Python Local', claude_llm: data.modelo_label || 'Sonnet 4.6', multi_modelo: 'Multi-Modelo' }[data.modo] || data.modo;
  const modo = baseLabel;
  const scoreConsenso = data.score_consenso != null ? (data.score_consenso * 100).toFixed(0) + '%' : '—';

  document.getElementById('kpi-grid').innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">Transações</div>
      <div class="kpi-value blue">${totalTx}</div>
      <div class="kpi-sub">${data.extratos?.length ?? 0} conta(s)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Anomalias</div>
      <div class="kpi-value ${totalAnom > 0 ? 'kpi-value' : 'green'}" style="${totalAnom>0?'color:var(--red)':''}">${totalAnom}</div>
      <div class="kpi-sub">${totalAnom === 0 ? 'Nenhuma detectada' : 'Ver detalhes abaixo'}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Modo</div>
      <div class="kpi-value" style="font-size:1.1rem;font-family:'Inter',sans-serif;font-weight:700">${modo}</div>
      <div class="kpi-sub">${data.stop_reason ?? (data.score_consenso != null ? 'Consenso calculado' : 'Concluído')}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Score Consenso</div>
      <div class="kpi-value ${data.score_consenso != null ? 'purple' : 'text-muted'}">${scoreConsenso}</div>
      <div class="kpi-sub">${data.score_consenso != null ? `${data.modelos?.length ?? 0} modelos` : 'Modo único'}</div>
    </div>`;

  // Export bar
  document.getElementById('export-bar').innerHTML = `
    <a class="btn btn-outline btn-sm" href="${API}/export/html/${_reportId}" target="_blank" rel="noopener"
       aria-label="Baixar relatório HTML">
      <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      Baixar HTML
    </a>
    <a class="btn btn-outline btn-sm" href="${API}/export/xlsx/${_reportId}" target="_blank" rel="noopener"
       aria-label="Baixar planilha XLSX">
      <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
      </svg>
      Baixar XLSX
    </a>`;

  // Anomalias
  const anomalias = data.anomalias ?? [];
  const secAnom = document.getElementById('anomalias-section');
  if (anomalias.length > 0) {
    const html = anomalias.map(a => `
      <div class="anomalia-item ${a.severidade}">
        <span class="sev-badge ${a.severidade}">${a.severidade}</span>
        <div class="anomalia-content">
          <div class="anomalia-title">${esc(a.titulo)}</div>
          <div class="anomalia-detail">${esc(a.conta)} — ${esc(a.detalhe)}</div>
        </div>
        <span class="anomalia-valor">${a.valor != null ? 'R$ ' + a.valor.toLocaleString('pt-BR',{minimumFractionDigits:2}) : ''}</span>
      </div>`).join('');
    secAnom.innerHTML = `
      <div class="section-title">
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        Anomalias Detectadas (${anomalias.length})
      </div>
      <div class="anomalia-list" role="list" aria-label="Anomalias detectadas">${html}</div>`;
  } else {
    secAnom.innerHTML = `<div style="display:flex;align-items:center;gap:8px;color:var(--green);font-weight:600;margin-bottom:20px">
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
      Nenhuma anomalia detectada
    </div>`;
  }

  // Relatório principal
  const relHtml = data.relatorio_html || (data.relatorio_md ? marked.parse(data.relatorio_md) : '');
  document.getElementById('report-html').innerHTML = relHtml || '<p class="text-muted">Relatório não disponível.</p>';

  // Relatórios individuais (multi-model)
  const relInd = data.relatorios_individuais;
  const secInd = document.getElementById('individual-section');
  if (relInd && Object.keys(relInd).length > 0) {
    secInd.classList.remove('hidden');
    const items = Object.entries(relInd).map(([label, texto], i) => `
      <div class="accordion-item">
        <button class="accordion-btn" aria-expanded="${i===0}" onclick="toggleAccordion(this)">
          <span>${esc(label)}</span>
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        <div class="accordion-content report-body ${i===0?'open':''}">${marked.parse(texto)}</div>
      </div>`).join('');
    document.getElementById('individual-accordion').innerHTML = items;
  } else {
    secInd.classList.add('hidden');
  }

  const panel = document.getElementById('result-panel');
  panel.style.display = 'block';
  panel.classList.add('active');
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  toast('Conciliação concluída com sucesso!', 'success');
}

function novaAnalise() {
  _arquivos = [];
  _reportId = null;
  renderFileList();
  atualizarSteps();
  atualizarBotaoCTA();
  document.getElementById('result-panel').style.display = 'none';
  document.getElementById('result-panel').classList.remove('active');
  document.getElementById('card-mode').classList.remove('hidden');
  document.getElementById('card-upload').classList.remove('hidden');
  document.getElementById('card-cta').classList.remove('hidden');
  document.getElementById('file-input').value = '';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function toggleAccordion(btn) {
  const expanded = btn.getAttribute('aria-expanded') === 'true';
  btn.setAttribute('aria-expanded', !expanded);
  btn.nextElementSibling.classList.toggle('open', !expanded);
}

/* ── Clientes ───────────────────────────────────────────────────── */
async function carregarClientes() {
  const tbody = document.getElementById('clientes-tbody');
  tbody.innerHTML = '<tr><td colspan="5" class="text-muted" style="text-align:center;padding:24px">Carregando…</td></tr>';
  try {
    const r = await fetch(`${API}/clientes`);
    if (!r.ok) throw new Error(r.statusText);
    const lista = await r.json();
    if (!lista.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-muted" style="text-align:center;padding:32px">Nenhum cliente cadastrado.</td></tr>';
      return;
    }
    tbody.innerHTML = lista.map(c => `
      <tr>
        <td><strong>${esc(c.nome)}</strong></td>
        <td style="font-family:'JetBrains Mono',monospace;font-size:.8rem">${c.cnpj ? formatCNPJ(c.cnpj) : '—'}</td>
        <td>${c.email ? esc(c.email) : '—'}</td>
        <td><span class="plano-badge ${c.plano}">${c.plano}</span></td>
        <td><span class="status-dot ${c.ativo ? 'ativo' : ''}">${c.ativo ? 'Ativo' : 'Inativo'}</span></td>
      </tr>`).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--red)">${esc(e.message)}</td></tr>`;
  }
}

function abrirModalCliente() {
  document.getElementById('modal-cliente').classList.add('open');
  document.getElementById('inp-nome').focus();
}
function fecharModal() {
  document.getElementById('modal-cliente').classList.remove('open');
  document.getElementById('form-cliente').reset();
  document.querySelectorAll('.error').forEach(e => e.style.display = 'none');
}

document.getElementById('modal-cliente').addEventListener('keydown', e => {
  if (e.key === 'Escape') fecharModal();
});

async function submitCliente(e) {
  e.preventDefault();
  const nome  = document.getElementById('inp-nome').value.trim();
  const cnpj  = document.getElementById('inp-cnpj').value.trim();
  const email = document.getElementById('inp-email').value.trim();
  const tel   = document.getElementById('inp-tel').value.trim();
  const plano = document.getElementById('inp-plano').value;

  let ok = true;
  const errNome = document.getElementById('err-nome');
  const errCnpj = document.getElementById('err-cnpj');
  errNome.style.display = 'none';
  errCnpj.style.display = 'none';

  if (!nome) { errNome.style.display = 'block'; ok = false; document.getElementById('inp-nome').focus(); }

  if (!ok) return;

  const btn = document.getElementById('btn-salvar-cliente');
  btn.disabled = true; btn.textContent = 'Salvando…';

  const body = { nome, plano };
  if (cnpj)  body.cnpj  = cnpj.replace(/\D/g, '');
  if (email) body.email = email;
  if (tel)   body.telefone = tel;

  try {
    const r = await fetch(`${API}/clientes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      if (r.status === 409) { errCnpj.textContent = 'CNPJ já cadastrado.'; errCnpj.style.display = 'block'; }
      else if (r.status === 422) {
        const detail = err.detail?.[0]?.msg || 'Dados inválidos.';
        if (detail.toLowerCase().includes('cnpj')) { errCnpj.textContent = detail; errCnpj.style.display = 'block'; }
        else toast('Erro de validação: ' + detail, 'error');
      } else throw new Error(err.detail || r.statusText);
      return;
    }
    fecharModal();
    toast('Cliente cadastrado com sucesso!', 'success');
    carregarClientes();
  } catch(err) {
    toast('Erro: ' + err.message, 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Cadastrar';
  }
}

/* ── Histórico ──────────────────────────────────────────────────── */
function atualizarHistorico() {
  const container = document.getElementById('relatorios-lista');
  if (!container) return;
  if (!_historicoRelatorios.length) {
    container.innerHTML = '<div class="text-muted" style="padding:24px;text-align:center">Nenhum relatório no histórico ainda.</div>';
    return;
  }
  const modos = { simulacao_local: 'Python Local', claude_llm: 'Claude LLM', multi_modelo: 'Multi-Modelo' };
  const cabecalho = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <span class="text-muted" style="font-size:.78rem">${_historicoRelatorios.length} relatório(s) persistido(s) localmente</span>
      <button class="btn btn-outline btn-sm" onclick="limparHistorico()" aria-label="Limpar histórico local">Limpar histórico</button>
    </div>`;
  container.innerHTML = cabecalho + _historicoRelatorios.slice().reverse().map(r => {
    const label = r.modelo_label ? `${modos[r.modo] || r.modo} (${r.modelo_label})` : (modos[r.modo] || r.modo);
    const dt = r.ts instanceof Date ? r.ts : new Date(r.ts);
    const data = dt.toLocaleString('pt-BR');
    const score = r.score != null ? ` · Score ${(r.score*100).toFixed(0)}%` : '';
    return `
    <div class="card" style="margin-bottom:12px">
      <div class="card-body" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap">
        <div>
          <strong style="font-size:.9rem">${r.id}</strong>
          <div style="font-size:.78rem;color:var(--muted);margin-top:2px">
            ${label} · ${data}${score}
          </div>
          <div style="font-size:.72rem;color:var(--muted);margin-top:3px">
            ${r.total_tx ?? 0} transação(ões) · ${r.total_anom ?? 0} anomalia(s)
          </div>
        </div>
        <div style="display:flex;gap:8px">
          <a class="btn btn-outline btn-sm" href="${API}/export/html/${r.id}" target="_blank" rel="noopener">HTML</a>
          <a class="btn btn-outline btn-sm" href="${API}/export/xlsx/${r.id}" target="_blank" rel="noopener">XLSX</a>
          <a class="btn btn-outline btn-sm" href="${API}/export/pdf/${r.id}" target="_blank" rel="noopener">PDF</a>
        </div>
      </div>
    </div>`;
  }).join('');
}

/* ── Charts (Chart.js) ──────────────────────────────────────────── */
function paletaCharts() {
  const tema = document.documentElement.getAttribute('data-theme') || 'light';
  return tema === 'dark'
    ? {
        text: '#e6edf7', muted: '#9aa6c0', grid: 'rgba(255,255,255,.08)',
        cores: ['#4dc8ff','#1e6fd9','#6fe3ff','#38e1a3','#ffb84d','#ff5c6c','#a78bfa','#ffe066','#f472b6','#22d3ee'],
        critico: '#ff5c6c', alerta: '#ffb84d', atencao: '#ffe066',
      }
    : {
        text: '#1f2b4d', muted: '#5a6b8a', grid: 'rgba(15,30,70,.08)',
        cores: ['#1e6fd9','#0a3a7a','#4dc8ff','#10b981','#f59e0b','#ef4444','#7c3aed','#eab308','#ec4899','#06b6d4'],
        critico: '#dc2626', alerta: '#d97706', atencao: '#ca8a04',
      };
}

function destruirCharts() {
  [_chartCategorias, _chartAnomalias, _chartFluxo,
   _chartContrapartes, _chartRadar, _chartSemana
  ].forEach(c => { try { c?.destroy(); } catch {} });
  _chartCategorias = _chartAnomalias = _chartFluxo = null;
  _chartContrapartes = _chartRadar = _chartSemana = null;
}

function agregarContrapartes(extratos) {
  const mapa = new Map();
  (extratos || []).forEach(e => {
    (e.transacoes || []).forEach(t => {
      const nome = (t.nome || t.memo || 'Sem identificação').toString().slice(0, 40);
      const prev = mapa.get(nome) || 0;
      mapa.set(nome, prev + Math.abs(t.valor || 0));
    });
  });
  const arr = [...mapa.entries()].sort((a,b) => b[1] - a[1]).slice(0, 10);
  return { labels: arr.map(x => x[0]), valores: arr.map(x => x[1]) };
}

function agregarConformidade(extratos, anomalias) {
  const txs = (extratos || []).flatMap(e => e.transacoes || []);
  const total = txs.length || 1;
  const classificadas = txs.filter(t => (t.categoria || classificarCliente(t)) !== 'Outros').length;
  const comData       = txs.filter(t => !!t.data).length;
  const comMemo       = txs.filter(t => !!t.memo).length;
  const semAnomCrit   = total - (anomalias || []).filter(a => a.severidade === 'critico').length;
  const equilibrio = (() => {
    const c = txs.filter(t => t.valor > 0).reduce((s,t) => s + t.valor, 0);
    const d = Math.abs(txs.filter(t => t.valor < 0).reduce((s,t) => s + t.valor, 0));
    if (c + d === 0) return 0;
    return Math.min(c, d) / Math.max(c, d) * 100;
  })();
  return {
    labels: ['Classificação', 'Datas válidas', 'Descrição preenchida', 'Sem críticos', 'Equilíbrio C/D'],
    valores: [
      (classificadas / total) * 100,
      (comData / total) * 100,
      (comMemo / total) * 100,
      (semAnomCrit / total) * 100,
      equilibrio,
    ].map(v => Math.round(v)),
  };
}

function agregarPorDiaSemana(extratos) {
  const dias = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
  const credito = [0,0,0,0,0,0,0];
  const debito  = [0,0,0,0,0,0,0];
  (extratos || []).forEach(e => {
    (e.transacoes || []).forEach(t => {
      if (!t.data) return;
      const d = new Date(t.data + 'T00:00:00');
      const dow = d.getDay();
      if (t.valor > 0) credito[dow] += t.valor;
      else debito[dow] += Math.abs(t.valor);
    });
  });
  return { labels: dias, credito, debito };
}

function rankingAnomalias(anomalias) {
  return (anomalias || [])
    .slice()
    .sort((a, b) => {
      const peso = { critico: 3, alerta: 2, atencao: 1 };
      const pa = (peso[a.severidade] || 0) * 1e9 + Math.abs(a.valor || 0);
      const pb = (peso[b.severidade] || 0) * 1e9 + Math.abs(b.valor || 0);
      return pb - pa;
    })
    .slice(0, 5);
}

function renderizarRankingRisco(anomalias) {
  const wrap = document.getElementById('ranking-risco');
  if (!wrap) return;
  const top = rankingAnomalias(anomalias);
  if (!top.length) {
    wrap.innerHTML = `
      <div class="risco-empty">
        <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        Nenhum risco detectado
      </div>`;
    return;
  }
  wrap.innerHTML = top.map((a, i) => {
    const valor = a.valor != null ? 'R$ ' + Math.abs(a.valor).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) : '—';
    return `
      <div class="risco-item">
        <div class="risco-pos">${i + 1}</div>
        <div class="risco-info">
          <div class="risco-tit"><span class="sev-dot ${a.severidade}"></span>${esc(a.titulo || a.tipo || 'Anomalia')}</div>
          <div class="risco-sub">${esc(a.conta || '')} · ${esc(a.detalhe || '')}</div>
        </div>
        <div class="risco-val ${a.severidade}">${valor}</div>
      </div>`;
  }).join('');
}

function agregarCategorias(extratos) {
  const mapa = new Map();
  (extratos || []).forEach(e => {
    (e.transacoes || []).forEach(t => {
      const cat = (t.categoria || classificarCliente(t)).toString();
      const prev = mapa.get(cat) || 0;
      mapa.set(cat, prev + Math.abs(t.valor || 0));
    });
  });
  const arr = [...mapa.entries()].sort((a,b) => b[1] - a[1]).slice(0, 8);
  return { labels: arr.map(x => x[0]), valores: arr.map(x => x[1]) };
}

function classificarCliente(t) {
  const txt = ((t.memo || '') + ' ' + (t.nome || '')).toLowerCase();
  if (/folha|salario|salário/.test(txt)) return 'Folha';
  if (/imposto|darf|gps|inss|icms|iss/.test(txt)) return 'Tributos';
  if (/fornecedor|pagamento/.test(txt)) return 'Fornecedores';
  if (/cliente|recebimento/.test(txt)) return 'Recebimentos';
  if (/tarifa|taxa|juros|iof/.test(txt)) return 'Taxas';
  if (/transfer|ted|pix|doc/.test(txt)) return 'Transferências';
  return 'Outros';
}

function agregarAnomaliasPorSeveridade(anomalias) {
  const c = { critico: 0, alerta: 0, atencao: 0 };
  (anomalias || []).forEach(a => { if (c[a.severidade] != null) c[a.severidade]++; });
  return c;
}

function agregarFluxoDiario(extratos) {
  const mapa = new Map();
  (extratos || []).forEach(e => {
    (e.transacoes || []).forEach(t => {
      if (!t.data) return;
      const k = t.data;
      const acc = mapa.get(k) || { credito: 0, debito: 0 };
      if (t.valor > 0) acc.credito += t.valor; else acc.debito += Math.abs(t.valor);
      mapa.set(k, acc);
    });
  });
  const datas = [...mapa.keys()].sort();
  return {
    labels: datas,
    credito: datas.map(d => mapa.get(d).credito),
    debito:  datas.map(d => mapa.get(d).debito),
  };
}

function renderizarCamadasAuditoria(data) {
  const wrap = document.getElementById('audit-layers');
  if (!wrap) return;
  const totalTx  = (data.extratos || []).reduce((s, e) => s + (e.qtd || 0), 0);
  const totalCred = (data.extratos || []).reduce((s, e) =>
    s + (e.transacoes || []).filter(t => t.valor > 0).reduce((a,t) => a + t.valor, 0), 0);
  const totalDeb = (data.extratos || []).reduce((s, e) =>
    s + (e.transacoes || []).filter(t => t.valor < 0).reduce((a,t) => a + Math.abs(t.valor), 0), 0);
  const sev = agregarAnomaliasPorSeveridade(data.anomalias);
  const totalAnom = (data.anomalias || []).length;

  // Saúde da conciliação: invertido proporcional a anomalias críticas
  const saude = totalTx === 0 ? 0 : Math.max(0, 100 - (sev.critico * 18 + sev.alerta * 7 + sev.atencao * 2));
  const saudeClass = saude >= 85 ? 'l-ok' : saude >= 60 ? 'l-alerta' : 'l-critico';

  const fmt = n => 'R$ ' + n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  wrap.innerHTML = `
    <div class="audit-layer ${saudeClass}">
      <div class="lbl">Saúde da Conciliação</div>
      <div class="val">${saude.toFixed(0)}<span style="font-size:14px;color:var(--muted);font-weight:600">/100</span></div>
      <div class="sub">${sev.critico} crítico(s) · ${sev.alerta} alerta(s)</div>
    </div>
    <div class="audit-layer">
      <div class="lbl">Volume Total</div>
      <div class="val">${totalTx}</div>
      <div class="sub">${(data.extratos || []).length} conta(s) auditada(s)</div>
    </div>
    <div class="audit-layer l-ok">
      <div class="lbl">Total Crédito</div>
      <div class="val" style="font-size:18px">${fmt(totalCred)}</div>
      <div class="sub">Entrada consolidada</div>
    </div>
    <div class="audit-layer l-critico">
      <div class="lbl">Total Débito</div>
      <div class="val" style="font-size:18px">${fmt(totalDeb)}</div>
      <div class="sub">Saída consolidada · Líquido: ${fmt(totalCred - totalDeb)}</div>
    </div>`;
}

function renderizarCharts(data) {
  renderizarCamadasAuditoria(data);
  renderizarRankingRisco(data.anomalias);
  if (typeof Chart === 'undefined') { return; }
  destruirCharts();
  const pal = paletaCharts();
  Chart.defaults.color = pal.text;
  Chart.defaults.borderColor = pal.grid;
  Chart.defaults.font.family = "'Inter','Segoe UI',sans-serif";

  const cv1 = document.getElementById('chart-categorias');
  const cv2 = document.getElementById('chart-anomalias');
  const cv3 = document.getElementById('chart-fluxo');

  if (cv1) {
    const { labels, valores } = agregarCategorias(data.extratos);
    _chartCategorias = new Chart(cv1, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data: valores, backgroundColor: pal.cores, borderWidth: 2, borderColor: 'transparent' }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '62%',
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12, font: { size: 11 } } },
          tooltip: { callbacks: { label: c => `${c.label}: R$ ${c.parsed.toLocaleString('pt-BR',{minimumFractionDigits:2})}` } },
        },
      },
    });
  }

  if (cv2) {
    const c = agregarAnomaliasPorSeveridade(data.anomalias);
    _chartAnomalias = new Chart(cv2, {
      type: 'bar',
      data: {
        labels: ['Crítico','Alerta','Atenção'],
        datasets: [{
          data: [c.critico, c.alerta, c.atencao],
          backgroundColor: [pal.critico, pal.alerta, pal.atencao],
          borderRadius: 8, borderSkipped: false, maxBarThickness: 64,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: pal.grid } },
        },
      },
    });
  }

  if (cv3) {
    const f = agregarFluxoDiario(data.extratos);
    _chartFluxo = new Chart(cv3, {
      type: 'line',
      data: {
        labels: f.labels,
        datasets: [
          { label: 'Crédito', data: f.credito, borderColor: pal.cores[3], backgroundColor: 'rgba(56,225,163,.12)', tension: .35, fill: true, pointRadius: 2 },
          { label: 'Débito',  data: f.debito,  borderColor: pal.cores[5], backgroundColor: 'rgba(255,92,108,.12)', tension: .35, fill: true, pointRadius: 2 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
        scales: {
          x: { grid: { color: pal.grid }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
          y: { grid: { color: pal.grid }, ticks: { callback: v => 'R$ ' + Number(v).toLocaleString('pt-BR') } },
        },
      },
    });
  }

  const cv4 = document.getElementById('chart-contrapartes');
  if (cv4) {
    const c = agregarContrapartes(data.extratos);
    _chartContrapartes = new Chart(cv4, {
      type: 'bar',
      data: {
        labels: c.labels,
        datasets: [{
          data: c.valores,
          backgroundColor: pal.cores[0],
          borderRadius: 6, borderSkipped: false, maxBarThickness: 18,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => 'R$ ' + Number(ctx.parsed.x).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) } },
        },
        scales: {
          x: { grid: { color: pal.grid }, ticks: { callback: v => 'R$ ' + Number(v).toLocaleString('pt-BR') } },
          y: { grid: { display: false }, ticks: { font: { size: 11 } } },
        },
      },
    });
  }

  const cv5 = document.getElementById('chart-radar');
  if (cv5) {
    const r = agregarConformidade(data.extratos, data.anomalias);
    _chartRadar = new Chart(cv5, {
      type: 'radar',
      data: {
        labels: r.labels,
        datasets: [{
          label: 'Conformidade (%)',
          data: r.valores,
          backgroundColor: 'rgba(30,111,217,.18)',
          borderColor: pal.cores[0],
          borderWidth: 2,
          pointBackgroundColor: pal.cores[0],
          pointRadius: 4,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.label}: ${c.parsed.r}%` } } },
        scales: {
          r: {
            min: 0, max: 100,
            grid: { color: pal.grid },
            angleLines: { color: pal.grid },
            pointLabels: { color: pal.text, font: { size: 10 } },
            ticks: { display: false, stepSize: 25 },
          },
        },
      },
    });
  }

  const cv6 = document.getElementById('chart-semana');
  if (cv6) {
    const s = agregarPorDiaSemana(data.extratos);
    _chartSemana = new Chart(cv6, {
      type: 'bar',
      data: {
        labels: s.labels,
        datasets: [
          { label: 'Crédito', data: s.credito, backgroundColor: pal.cores[3], borderRadius: 5, stack: 'x' },
          { label: 'Débito',  data: s.debito,  backgroundColor: pal.cores[5], borderRadius: 5, stack: 'x' },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, grid: { color: pal.grid }, ticks: { callback: v => 'R$ ' + Number(v).toLocaleString('pt-BR') } },
        },
      },
    });
  }
}

/* ── Health check ───────────────────────────────────────────────── */
async function verificarHealth() {
  const badge = document.getElementById('db-badge');
  try {
    const r = await fetch(`${API}/health`);
    const d = await r.json();
    badge.textContent = d.banco_dados === 'ok' ? 'DB: online' : 'DB: ' + d.banco_dados;
    badge.className = 'badge-db ' + (d.banco_dados === 'ok' ? '' : 'offline');
  } catch {
    badge.textContent = 'DB: erro';
    badge.className = 'badge-db offline';
  }
}

/* ── Utilitários ────────────────────────────────────────────────── */
function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024*1024) return (b/1024).toFixed(1) + ' KB';
  return (b/1024/1024).toFixed(1) + ' MB';
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatCNPJ(s) {
  const d = s.replace(/\D/g,'');
  if (d.length !== 14) return s;
  return `${d.slice(0,2)}.${d.slice(2,5)}.${d.slice(5,8)}/${d.slice(8,12)}-${d.slice(12)}`;
}

function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.setAttribute('role', 'alert');
  el.innerHTML = `<span>${esc(msg)}</span>`;
  c.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

/* ── Init ───────────────────────────────────────────────────────── */
verificarHealth();
atualizarHistorico();
window.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'd') {
    e.preventDefault();
    toggleTema();
  }
});
