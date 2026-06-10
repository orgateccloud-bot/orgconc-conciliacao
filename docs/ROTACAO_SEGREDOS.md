# Rotação de Segredos — Runbook (P2 #13)

> Procedimentos para rotacionar cada segredo do OrgConc com impacto e ordem
> corretos. Onde ficam: Railway (env `production`, serviço `web`) e Supabase.
> Cadência sugerida: **semestral** ou imediatamente após suspeita de exposição.

## Inventário

| Segredo | Onde | Impacto da rotação |
|---|---|---|
| `ORGCONC_JWT_SECRET` | Railway | **Invalida todos os access tokens** (sessões ativas caem; refresh reemite) |
| `ORGCONC_ADMIN_SENHA_HASH` | Railway | Troca a senha do admin-bootstrap por env |
| `ORGCONC_AUTH_TOKEN` (service token) | Railway + scripts/CI que o usam | Quebra integrações que usam o token antigo |
| `ANTHROPIC_API_KEY` | Railway | Sem impacto de sessão; LLM passa a usar a chave nova |
| Senha do role `app_orgconc` (runtime DB) | Supabase + `DATABASE_URL` no Railway | Conexões novas usam a senha nova |
| Senha do owner / `ALEMBIC_DATABASE_URL` | Supabase + Railway | Só migrations (preDeploy) |
| `SENTRY_DSN` | Railway | Telemetria |

## Procedimentos

### 1. `ORGCONC_JWT_SECRET` (access tokens)
1. Gerar: `openssl rand -hex 32` (≥ 32 chars — produção rejeita fraco).
2. Railway → web → Variables → atualizar → redeploy.
3. Efeito: access tokens antigos passam a dar 401; o frontend renova via
   `/auth/refresh` (cookie httpOnly) — **refresh tokens NÃO dependem do JWT
   secret** (são opacos, sha256 no banco), então a renovação é transparente;
   sessões só caem de vez se o refresh também for revogado.
4. Verificar: login novo OK; `POST /auth/refresh` 200.

### 2. Senha do `app_orgconc` (runtime, NOBYPASSRLS)
1. No Supabase (SQL editor, como owner):
   `ALTER ROLE app_orgconc PASSWORD '<nova>';`
2. Atualizar `DATABASE_URL` no Railway (mesma URL, senha nova) → redeploy.
3. Verificar `/health` → `banco_dados: online` e uma listagem autenticada.
4. **Nunca** voltar o runtime para o role `postgres` (bypassaria RLS).

### 3. `ORGCONC_AUTH_TOKEN` (service token)
1. Gerar novo (`openssl rand -base64 24`), atualizar no Railway e em TODOS os
   consumidores (CI usa `e2e-ci-token` próprio do workflow — não confundir).
2. Lembrete: em produção o service token é **rejeitado** (só JWT); ele só
   habilita "auth obrigatória" fora de prod. Rotação aqui é higiene.

### 4. `ANTHROPIC_API_KEY`
1. Console Anthropic → criar chave nova → atualizar Railway → redeploy →
   revogar a antiga no console (ordem: criar → trocar → revogar).

### 5. Pós-rotação (sempre)
- [ ] `/health` ok · login ok · uma conciliação simulada ok.
- [ ] Sentry sem novos erros de auth/DB.
- [ ] Registrar a rotação (data + segredos trocados, SEM valores) no CHANGELOG.

## Staging
Os segredos do env `staging` são exclusivos (nunca compartilhados com prod) —
rotação independente, mesmo procedimento, sem janela de cuidado.
