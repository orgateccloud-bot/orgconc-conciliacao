# Post-mortem — Produção ~32h sem banco no runtime (senha do app_orgconc)

**Data do incidente:** 2026-06-09 ~13:00 → 2026-06-10 21:58 (-03:00) · **Detecção:** 2026-06-10 ~21:45
**Severidade:** alta (funcionalidade central degradada), impacto percebido baixo (janela sem uso ativo).

## O que aconteceu (timeline)

- **09/06 ~13:00** — primeiro deploy retido com `Banco nao configurado — persistencia JSON local`
  no startup. Todos os deploys seguintes (rodadas #113–#122) bootaram no mesmo estado.
- **09–10/06** — produção no ar em modo degradado: `DB_DISPONIVEL=False` → login de usuários
  de org, refresh de sessão, clientes/conciliações/transações respondendo 503; apenas o
  admin-env logava. Migrations continuaram passando no preDeploy (via `ALEMBIC_DATABASE_URL`).
- **10/06 ~21:45** — detectado durante a verificação pós-deploy do #122 (logs do worker da fila).
- **10/06 21:58** — corrigido: senha do role redefinida via conexão owner + `DATABASE_URL`
  atualizada no Railway + redeploy. `Banco configurado` + worker de jobs no ar.

## Impacto

~32h sem persistência/auth de usuários de org em produção. Sem perda de dados (o banco em si
nunca caiu). Sem relatos de usuários na janela.

## Causa raiz

`password authentication failed for user "app_orgconc"`: a senha na `DATABASE_URL` do Railway
não correspondia à senha do role no banco (rotação parcial — um lado mudou sem o outro).
O `ALEMBIC_DATABASE_URL` (user `postgres.<ref>`, owner) permaneceu válido, então o preDeploy
de cada deploy passava — mascarando o problema.

## Por que ninguém notou por 32h

1. `_db_ping_sync` engolia a exceção (`except: pass` + retry) — o erro real nunca foi logado.
2. `/health` de produção responde `{"status":"ok"}` sem o estado do banco (não expõe infra
   por design) — o monitor sintético nunca falhou.
3. O fallback de login do admin-env devolve 401 para credencial errada igual ao caminho com
   banco — login "parecia" funcionar.

## Diagnóstico que funcionou (sem credenciais, reproduzível)

- **Sonda:** `POST /auth/refresh` sem cookie → **503** = runtime sem DB · **401** = DB ok.
  (O login NÃO serve de sonda: o fallback admin-env responde 401 nos dois estados.)
- Migrations passam mas o runtime falha → comparar `DATABASE_URL` × `ALEMBIC_DATABASE_URL`
  (no incidente: mesmo pooler/porta, users diferentes → problema do user/credencial).
- Handshake no pooler com user-sonda inexistente prova o pooler vivo (resposta `EAUTHQUERY`
  rápida) sem credencial alguma.

## Correção e prevenções (links)

- **Correção:** `ALTER ROLE app_orgconc PASSWORD ...` via conexão owner → aguardar ~30–60s
  (o Supavisor CACHEIA credenciais; o teste imediato falha) → atualizar `DATABASE_URL` no
  Railway → redeploy. Host direto `db.<ref>.supabase.co` não resolve mais — usar só o pooler.
- **Prevenção 1 (#123):** `_db_ping_sync` agora loga warning por tentativa (tipo + 1ª linha
  do erro, sem credencial) e error final explícito.
- **Prevenção 2 (#123):** monitor sintético ganhou o step "Runtime com banco" (sonda
  `/auth/refresh` a cada 30min) — esse modo de falha alarma em ≤30min.
- **Processo:** rotação de segredo de DB deve seguir `docs/ROTACAO_SEGREDOS.md` de ponta a
  ponta (role + variável + redeploy + sonda) na MESMA janela.
