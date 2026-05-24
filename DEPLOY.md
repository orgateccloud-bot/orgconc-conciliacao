# Guia de Deploy — Orgconc

## URLs do Projeto

- **Frontend (GitHub Pages):** https://orgateccloud-bot.github.io/orgconc-conciliacao/
- **Login:** https://orgateccloud-bot.github.io/orgconc-conciliacao/frontend/login.html
- **Dashboard:** https://orgateccloud-bot.github.io/orgconc-conciliacao/frontend/dashboard_trust.html
- **Repositório:** https://github.com/orgateccloud-bot/orgconc-conciliacao

---

## 1. Frontend (GitHub Pages) — Automático

O frontend é publicado automaticamente via GitHub Actions a cada push na branch `main`.

**Arquivos publicados:**
- `frontend/login.html` — Página de entrada com autenticação JWT + Supabase
- `frontend/dashboard_trust.html` — Dashboard principal com API e conciliação
- `frontend/index.html` — Landing page

---

## 2. Backend (API FastAPI)

### Pré-requisitos
- Python 3.11+
- Conta no [Railway](https://railway.app), [Render](https://render.com) ou servidor próprio

### Deploy no Railway (recomendado)

```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login e deploy
railway login
railway init
railway up
```

### Deploy Manual (Servidor/VPS)

```bash
# Clonar repositório
git clone https://github.com/orgateccloud-bot/orgconc-conciliacao.git
cd orgconc-conciliacao/api

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp ../.env.example .env
nano .env  # Preencher valores abaixo

# Iniciar servidor
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Variáveis de Ambiente Obrigatórias

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Banco de dados
DATABASE_URL=postgresql://user:pass@host:5432/orgconc

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Autenticação
JWT_SECRET=seu-segredo-jwt-256bits
ORGCONC_AUTH_TOKEN=token-api-interno

# Admin
ORGCONC_ADMIN_EMAIL=admin@empresa.com
ORGCONC_ADMIN_SENHA_HASH=bcrypt-hash

# CORS (separar por vírgula)
ORGCONC_CORS_ORIGINS=https://orgateccloud-bot.github.io,http://localhost:3000

# Upload
ORGCONC_MAX_UPLOAD_MB=50
ORGCONC_MAX_UPLOAD_TOTAL_MB=500

# Servidor
HOST=0.0.0.0
PORT=8000
WORKERS=2
```

---

## 3. Supabase — Configuração

### Criar Projeto Supabase
1. Acessar https://supabase.com e criar conta
2. Criar novo projeto: **orgconc**
3. Anotar **Project URL** e **anon key** (Settings > API)

### Executar SQL de Setup

No painel do Supabase, ir em **SQL Editor** e executar o arquivo `supabase/setup.sql`:

```bash
# Tabelas criadas:
# - clientes        (id, nome, cnpj, status, criado_em)
# - conciliacoes    (id, cliente_id, status, periodo, criado_em)
# - transacoes      (id, conciliacao_id, data, valor, tipo, descricao)
# - anomalias       (id, conciliacao_id, tipo, descricao, valor, criado_em)
# - audit_log       (id, usuario, acao, tabela, registro_id, criado_em)
```

### Políticas de Segurança (RLS)
```sql
-- Habilitar RLS em todas as tabelas
ALTER TABLE clientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE conciliacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE transacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalias ENABLE ROW LEVEL SECURITY;

-- Política: usuários autenticados leem seus próprios dados
CREATE POLICY "usuarios_autenticados" ON clientes
  FOR ALL USING (auth.role() = 'authenticated');
```

---

## 4. GitHub Secrets (para CI/CD)

Configurar em **Settings > Secrets and variables > Actions**:

| Secret | Descrição |
|--------|-----------|
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_ANON_KEY` | Chave anon do Supabase |
| `JWT_SECRET` | Segredo JWT (mín. 32 chars) |
| `ORGCONC_AUTH_TOKEN` | Token de autenticação da API |

---

## 5. Conectar Frontend ao Backend

Após deploy do backend, atualizar a URL da API nos arquivos frontend:

```javascript
// Em frontend/login.html e frontend/dashboard_trust.html
const API_BASE = 'https://seu-backend.railway.app';  // ou Render/VPS
const SUPABASE_URL = 'https://xxxx.supabase.co';
const SUPABASE_ANON_KEY = 'sua-chave-anon';
```

---

## 6. Verificação Final

```bash
# Testar health do backend
curl https://seu-backend.railway.app/health

# Testar login
curl -X POST https://seu-backend.railway.app/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@empresa.com","senha":"suasenha"}'
```

**Resposta esperada do /health:**
```json
{"status": "ok", "version": "0.9.0", "database": "connected"}
```
