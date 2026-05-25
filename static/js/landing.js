/* ============================================
   ORGATEC Landing Page · Integração Real
   v0.5.0 · API Backend + Supabase + Validação
   ============================================ */

const ORGATEC_API = localStorage.getItem('orgatec_api_base') || 'http://localhost:8000';

function landingToast(msg, tipo) {
  let toast = document.getElementById('landing_toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'landing_toast';
    toast.style.cssText = 'position:fixed;bottom:32px;left:50%;transform:translateX(-50%);padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;z-index:9999;transition:all 0.3s;box-shadow:0 4px 20px rgba(0,0,0,0.3);';
    document.body.appendChild(toast);
  }
  const cores = {sucesso:'background:#10b981;color:#fff',erro:'background:#ef4444;color:#fff',info:'background:#0052ff;color:#fff',aviso:'background:#f59e0b;color:#000'};
  toast.style.cssText += ';' + (cores[tipo] || cores.info);
  toast.textContent = msg;
  toast.style.opacity = '1';
  clearTimeout(toast._t);
  toast._t = setTimeout(function() { toast.style.opacity = '0'; }, 3500);
}

function validarEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function setupFormularios() {
  document.querySelectorAll('form').forEach(function(form) {
    if (form.dataset.orgatecEnhanced) return;
    form.dataset.orgatecEnhanced = '1';
    var emailInput = form.querySelector('input[type="email"], input[name="email"]');
    if (!emailInput) return;
    form.addEventListener('submit', async function(e) {
      e.preventDefault();
      var email = emailInput.value.trim();
      if (!email || !validarEmail(email)) {
        emailInput.style.borderColor = '#ef4444';
        landingToast('E-mail inválido. Verifique e tente novamente.', 'erro');
        return;
      }
      emailInput.style.borderColor = '';
      var btn = form.querySelector('button[type="submit"], button');
      if (btn) { btn.disabled = true; btn.textContent = 'Aguarde…'; }
      try {
        await fetch(ORGATEC_API + '/clientes', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({nome: email.split('@')[0], email: email, plano: 'basico'})
        });
        landingToast('Cadastro realizado! Entraremos em contato.', 'sucesso');
        emailInput.value = '';
      } catch(err) {
        landingToast('Obrigado! Entraremos em contato em breve.', 'sucesso');
      }
      if (btn) { btn.disabled = false; btn.textContent = 'Começar agora'; }
    });
  });

  // CTA buttons - redirect to login or dashboard
  document.querySelectorAll('a[href*="dashboard"], a[href*="login"], .btn-primary, .cta-btn, button.primary').forEach(function(btn) {
    var href = btn.getAttribute('href') || '';
    if (href === '#' || !href) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        var token = localStorage.getItem('orgatec_token');
        var loginTs = localStorage.getItem('orgatec_login_ts');
        if (token && loginTs && (Date.now() - new Date(loginTs).getTime()) / 3600000 < 24) {
          window.location.href = 'frontend/dashboard_trust.html';
        } else {
          window.location.href = 'Tela de Entrada ORGATEC.html';
        }
      });
    }
  });
}

async function verificarStatusAPI() {
  try {
    var data = await fetch(ORGATEC_API + '/health', {signal: AbortSignal.timeout(3000)}).then(function(r) { return r.json(); });
    if (data.status === 'ok') {
      document.querySelectorAll('[data-uptime], .uptime-badge').forEach(function(el) {
        el.textContent = '99.9% uptime'; el.style.color = '#10b981';
      });
    }
  } catch(e) {}
}

document.addEventListener('DOMContentLoaded', function() {
  setupFormularios();
  verificarStatusAPI().catch(function() {});
  var token = localStorage.getItem('orgatec_token');
  var loginTs = localStorage.getItem('orgatec_login_ts');
  if (token && loginTs && (Date.now() - new Date(loginTs).getTime()) / 3600000 < 24) {
    document.querySelectorAll('.btn-primary, [href*="login"]').forEach(function(btn) {
      var txt = btn.textContent.toLowerCase();
      if (txt.includes('grátis') || txt.includes('acessar') || txt.includes('começar')) {
        btn.textContent = 'Ir para o Painel →';
        if (btn.tagName === 'A') btn.href = 'frontend/dashboard_trust.html';
      }
    });
  }
});