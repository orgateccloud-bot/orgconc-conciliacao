/* OrgConc /ui/ — extraido do inline script de static/index.html
 * Razao: CSP estrito (sem 'unsafe-inline') bloqueava o bloco inline.
 * Fix XSS: substituidas template strings com ${var} por createElement+textContent
 * nos pontos onde dados podem vir de input do usuario (nome de arquivo,
 * resposta JSON do backend).
 */
(function () {
  "use strict";

  const API = window.location.origin.startsWith("http")
    ? window.location.origin
    : "http://127.0.0.1:8765";
  let lastReportId = null;
  let logoDataUri = null;

  // Pre-carrega a logo em base64 para o PDF nao depender de fetch dinamico
  fetch(`${API}/logo-base64`)
    .then((r) => r.json())
    .then((d) => {
      logoDataUri = d.data_uri;
    })
    .catch(() => {});

  function baixar(fmt) {
    if (!lastReportId) {
      setStatus("Gere um relatório antes de baixar.", "err");
      return;
    }
    window.open(`${API}/export/${fmt}/${lastReportId}`, "_blank");
  }

  const EXTS_VALIDAS = new Set([".ofx", ".pdf", ".xml"]);

  function atualizarLista() {
    const fs = document.getElementById("files").files;
    const list = document.getElementById("file-list");
    list.replaceChildren();
    if (!fs.length) {
      const empty = document.createElement("div");
      empty.className = "file-item empty";
      empty.textContent = "Nenhum arquivo selecionado";
      list.appendChild(empty);
      return;
    }
    for (const f of fs) {
      const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
      if (!EXTS_VALIDAS.has(ext)) {
        setStatus(
          `Arquivo "${f.name}" não suportado. Use .ofx, .pdf ou .xml.`,
          "err",
        );
        document.getElementById("files").value = "";
        const empty = document.createElement("div");
        empty.className = "file-item empty";
        empty.textContent = "Nenhum arquivo selecionado";
        list.replaceChildren(empty);
        return;
      }
    }
    if (fs.length > 50) {
      setStatus("Máximo de 50 arquivos por vez.", "err");
      return;
    }
    for (const f of fs) {
      const kb = (f.size / 1024).toFixed(1);
      const item = document.createElement("div");
      item.className = "file-item";

      const ico = document.createElement("span");
      ico.className = "ico";
      ico.setAttribute("aria-hidden", "true");
      ico.innerHTML =
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';

      const name = document.createElement("span");
      name.className = "name";
      name.textContent = f.name; // SAFE: nome de arquivo entra como texto

      const size = document.createElement("span");
      size.className = "size";
      size.textContent = `${kb} KB`;

      item.append(ico, name, size);
      list.appendChild(item);
    }
  }

  function setStatus(msg, kind) {
    const el = document.getElementById("status");
    el.textContent = msg;
    el.className = "status " + (kind || "");
  }

  function renderAnomalias(anomalias) {
    const wrap = document.getElementById("anom-wrap");
    const grid = document.getElementById("anom-grid");
    const chips = document.getElementById("sev-chips");
    grid.replaceChildren();
    chips.replaceChildren();
    if (!anomalias.length) {
      wrap.style.display = "none";
      return;
    }

    const by = { critico: [], alerta: [], atencao: [] };
    for (const a of anomalias) (by[a.severidade] || by.atencao).push(a);
    const labels = {
      critico: "🔴 Críticos",
      alerta: "🟠 Alertas",
      atencao: "🟡 Atenção",
    };
    for (const k of ["critico", "alerta", "atencao"]) {
      if (by[k].length) {
        const chip = document.createElement("span");
        chip.className = `sev-chip ${k}`;
        chip.textContent = `${labels[k]} ${by[k].length}`;
        chips.appendChild(chip);
      }
    }

    const lista = [...by.critico, ...by.alerta, ...by.atencao.slice(0, 6)];
    for (const a of lista) {
      const card = document.createElement("div");
      // severidade controla classe — limitada a 3 valores conhecidos
      const sev = ["critico", "alerta", "atencao"].includes(a.severidade)
        ? a.severidade
        : "atencao";
      card.className = `anom ${sev}`;

      const tag = document.createElement("span");
      tag.className = "anom-tag";
      tag.textContent = a.tipo || "";

      const tt = document.createElement("div");
      tt.className = "anom-tt";
      tt.textContent = a.titulo || "";

      const cc = document.createElement("div");
      cc.className = "anom-cc";
      cc.textContent = a.conta || "";

      const dt = document.createElement("div");
      dt.className = "anom-dt";
      dt.textContent = a.detalhe || "";

      card.append(tag, tt, cc, dt);
      grid.appendChild(card);
    }
    if (by.atencao.length > 6) {
      const extra = document.createElement("div");
      extra.className = "anom atencao";
      extra.style.cssText =
        "display:flex;align-items:center;justify-content:center;font-style:italic;color:var(--muted);font-size:12px";
      extra.textContent = `+ ${by.atencao.length - 6} adicionais`;
      grid.appendChild(extra);
    }
    wrap.style.display = "block";
  }

  async function enviar(simular) {
    const files = document.getElementById("files").files;
    if (!files.length || files.length > 50) {
      setStatus("Selecione entre 1 e 50 arquivos.", "err");
      return;
    }

    const btns = document.querySelectorAll(".btn");
    btns.forEach((b) => (b.disabled = true));
    const btnActive = document.getElementById(simular ? "btn-sim" : "btn-llm");
    const originalContent = btnActive.innerHTML;
    btnActive.innerHTML = '<span class="spinner"></span> Processando...';
    setStatus(
      simular ? "Processando localmente..." : "Chamando Claude API...",
      "work",
    );

    const form = new FormData();
    for (const f of files) form.append("arquivos", f);

    const t0 = performance.now();
    try {
      const url = `${API}/conciliar/ofx${simular ? "?simular=true" : ""}`;
      const r = await fetch(url, { method: "POST", body: form });
      const dt = ((performance.now() - t0) / 1000).toFixed(2);
      const data = await r.json();

      if (!r.ok) {
        const err =
          data.detail?.anthropic_error || data.detail || JSON.stringify(data);
        setStatus(`HTTP ${r.status}: ${err}`, "err");
        return;
      }

      const metrics = document.getElementById("metrics");
      metrics.replaceChildren();
      const stats = [
        {
          label: "Modo",
          val: data.modo === "simulacao_local" ? "SIMULAÇÃO" : "CLAUDE LLM",
          accent: true,
        },
        { label: "Tempo", val: dt + "s" },
      ];
      for (const e of data.extratos || [])
        stats.push({ label: (e.conta || "").replace("AG ", ""), val: e.qtd + " tx" });
      if (data.anomalias)
        stats.push({ label: "Anomalias", val: data.anomalias.length, accent: true });
      if (data.usage) {
        stats.push({
          label: "Tokens entrada",
          val: data.usage.input_tokens.toLocaleString(),
        });
        stats.push({
          label: "Tokens saída",
          val: data.usage.output_tokens.toLocaleString(),
        });
      }
      for (const s of stats) {
        const m = document.createElement("div");
        m.className = "metric";
        const lb = document.createElement("div");
        lb.className = "lb";
        lb.textContent = s.label;
        const vl = document.createElement("div");
        vl.className = "vl" + (s.accent ? " accent" : "");
        vl.textContent = String(s.val);
        m.append(lb, vl);
        metrics.appendChild(m);
      }

      lastReportId = data.report_id || null;
      renderAnomalias(data.anomalias || []);
      // marked + DOMPurify ja saneiam o Markdown gerado pelo backend
      document.getElementById("relatorio").innerHTML = DOMPurify.sanitize(
        marked.parse(data.relatorio_md || ""),
      );
      document.getElementById("saida").style.display = "block";
      setStatus(`Concluído em ${dt}s.`, "ok");
      window.scrollTo({
        top: document.getElementById("saida").offsetTop - 20,
        behavior: "smooth",
      });
    } catch (e) {
      setStatus("Erro de conexão: " + e.message, "err");
    } finally {
      btns.forEach((b) => (b.disabled = false));
      btnActive.innerHTML = originalContent;
    }
  }

  async function gerarPDF() {
    if (!lastReportId) {
      setStatus("Gere um relatório antes de exportar PDF.", "err");
      return;
    }
    const btn = document.getElementById("btn-pdf");
    const original = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span> Renderizando PDF...';
    btn.disabled = true;

    if (!logoDataUri) {
      try {
        const r = await fetch(`${API}/logo-base64`);
        logoDataUri = (await r.json()).data_uri;
      } catch {}
    }

    let serverHtml = "";
    try {
      const r = await fetch(`${API}/export/html/${lastReportId}`);
      serverHtml = await r.text();
    } catch (e) {
      // fallback: monta inline com o que ja temos
    }

    const PAGE_W = 794; // A4 = 210mm @ 96dpi
    const el = document.createElement("div");
    el.style.cssText = `background:#fff;width:${PAGE_W}px;color:#1a202c;font-family:Inter,sans-serif;`;

    if (serverHtml) {
      const parser = new DOMParser();
      const doc = parser.parseFromString(serverHtml, "text/html");
      const wrap = doc.querySelector(".wrap") || doc.body;
      el.innerHTML = wrap.outerHTML;
      const serverStyle = doc.querySelector("style");
      if (serverStyle) {
        const s = document.createElement("style");
        s.textContent =
          serverStyle.textContent
            .replace(/body\s*\{/g, ".pdf-root {")
            .replace(/html, body\s*\{/g, ".pdf-root {")
            .replace(/\.wrap\s*\{/g, ".pdf-root .wrap {") +
          `
          .pdf-root h1, .pdf-root h2, .pdf-root h3 { page-break-after: avoid; }
          .pdf-root table, .pdf-root tr { page-break-inside: avoid; }
          .pdf-root .hd { padding: 22px 36px !important; }
          .pdf-root .hd .brand .nm { font-size: 22px !important; }
          .pdf-root .content { padding: 24px 36px 16px !important; font-size: 11px; line-height: 1.55; }
          .pdf-root .content h1 { font-size: 18px; margin-bottom: 10px; }
          .pdf-root .content h2 { font-size: 14px; margin: 16px 0 6px; }
          .pdf-root .content h3 { font-size: 12px; }
          .pdf-root .content p, .pdf-root .content li { font-size: 10.5px; }
          .pdf-root .content table { font-size: 9.5px; margin: 6px 0; }
          .pdf-root .content th, .pdf-root .content td { padding: 5px 8px; }
          .pdf-root .ft { padding: 10px 36px !important; font-size: 9px; }
        `;
        document.head.appendChild(s);
      }
      el.classList.add("pdf-root");
      el.querySelectorAll("img").forEach((img) => {
        if (
          logoDataUri &&
          (img.src.includes("/ui/logo.png") || img.alt === "ORGATEC")
        ) {
          img.src = logoDataUri;
        }
      });
    } else {
      const data = new Date().toLocaleString("pt-BR");
      const logoImg = logoDataUri
        ? `<img src="${logoDataUri}" style="width:58px;height:58px;">`
        : "";
      const reportHtml = document.getElementById("relatorio").innerHTML;
      el.innerHTML = `
        <div style="background:linear-gradient(135deg,#0a3a7a 0%,#1e6fd9 60%,#4dc8ff 100%);padding:22px 36px;color:#fff;display:flex;gap:16px;align-items:center;">
          ${logoImg}
          <div><div style="font-size:22px;font-weight:800;">ORGATEC</div><div style="font-size:9.5px;letter-spacing:2.5px;text-transform:uppercase;opacity:0.9;">Contabilidade &amp; Auditoria</div></div>
          <div style="margin-left:auto;text-align:right;font-size:10px;background:rgba(255,255,255,0.14);border:1px solid rgba(255,255,255,0.28);border-radius:8px;padding:7px 12px;">
            <div style="font-weight:700;letter-spacing:1.5px;font-size:9px;">RELATÓRIO DE CONCILIAÇÃO</div>
            <div style="font-size:11px;font-weight:600;margin-top:2px;">${data}</div>
          </div>
        </div>
        <div style="padding:24px 36px 16px;color:#1a202c;font-size:11px;line-height:1.55;">${reportHtml}</div>
        <div style="background:#f7fafc;padding:10px 36px;color:#718096;font-size:9px;border-top:1px solid #e2e8f0;display:flex;justify-content:space-between;">
          <div>© ORGATEC · orgatec.cloud@gmail.com</div>
          <div style="background:#eff6ff;color:#1e6fd9;padding:2px 9px;border-radius:999px;font-weight:600;">OrgAudi 1.0</div>
        </div>
      `;
    }
    document.body.appendChild(el);

    try {
      const imgs = el.querySelectorAll("img");
      await Promise.all(
        Array.from(imgs).map((img) =>
          img.complete
            ? null
            : new Promise((res) => {
                img.onload = img.onerror = res;
              }),
        ),
      );
      await html2pdf()
        .from(el)
        .set({
          margin: [0, 0, 0, 0],
          filename: `conciliacao_${new Date().toISOString().slice(0, 10)}.pdf`,
          image: { type: "jpeg", quality: 0.98 },
          html2canvas: {
            scale: 2,
            useCORS: true,
            backgroundColor: "#ffffff",
            logging: false,
            allowTaint: true,
            width: 794,
            windowWidth: 794,
          },
          jsPDF: {
            unit: "mm",
            format: "a4",
            orientation: "portrait",
            compress: true,
          },
          pagebreak: {
            mode: ["css", "legacy", "avoid-all"],
            avoid: ["tr", "h1", "h2", "h3", "table"],
          },
        })
        .save();
      setStatus("PDF gerado.", "ok");
    } catch (e) {
      setStatus("Erro ao gerar PDF: " + e.message, "err");
    } finally {
      document.body.removeChild(el);
      btn.innerHTML = original;
      btn.disabled = false;
    }
  }

  // ── Wiring (substitui handlers inline removidos do HTML) ────────────────
  document.addEventListener("DOMContentLoaded", () => {
    document
      .getElementById("files")
      .addEventListener("change", atualizarLista);

    document
      .getElementById("btn-sim")
      .addEventListener("click", () => enviar(true));
    document
      .getElementById("btn-llm")
      .addEventListener("click", () => enviar(false));

    document
      .getElementById("btn-html")
      .addEventListener("click", () => baixar("html"));
    document
      .getElementById("btn-xlsx")
      .addEventListener("click", () => baixar("xlsx"));
    document.getElementById("btn-pdf").addEventListener("click", gerarPDF);

    // Drag-and-drop visual
    const drop = document.getElementById("drop");
    ["dragenter", "dragover"].forEach((ev) =>
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.add("drag-over");
      }),
    );
    ["dragleave", "drop"].forEach((ev) =>
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.remove("drag-over");
      }),
    );
    drop.addEventListener("drop", (e) => {
      document.getElementById("files").files = e.dataTransfer.files;
      atualizarLista();
    });
  });
})();
