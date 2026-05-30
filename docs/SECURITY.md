# Segurança — OrgConc

> Modelo de ameaça, controles implementados e procedimento de reporte.

## 1. Modelo de ameaça (resumido)

| Vetor | Mitigação atual |
|---|---|
| **SQL Injection** | SQLAlchemy ORM exclusivamente; sem queries string |
| **XSS via LLM output** | `bleach.clean()` allowlist em todo HTML renderizado |
| **CSRF** | Endpoints mutadores exigem `Authorization: Bearer` (não cookies). Refresh em cookie httpOnly+SameSite=strict |
| **SSRF (WeasyPrint)** | `url_fetcher=_block` bloqueia qualquer fetch externo |
| **XML XXE** | `defusedxml` em todos os parsers |
| **Credential stuffing** | Rate-limit 10/min em `/auth/login`; constant-time compare via bcrypt |
| **JWT secret leak** | Boot falha se < 32 chars em prod; auto-gerado em dev (warning) |
| **PII em logs** | `mask_pii` automático: CPF/CNPJ/email/último octeto IP |
| **Refresh token replay** | Rotação obrigatória; reuso de token revogado retorna 401 |
| **Brute-force endpoints sensíveis** | Rate-limit por `sub` JWT (não só IP) |
| **Headers fracos** | CSP estrito, HSTS, X-Frame-Options DENY, COOP/CORP same-origin |
| **CORS aberto** | Lista explícita; obrigatório em prod (`_validate_production_env`) |
| **Secrets no código** | CI bloqueia commit com `sk-ant-*` ou `.env` |
| **Vuln em deps** | `pip-audit` + `npm audit` + Trivy no CI |
| **Audit trail** | `audit_log` registra toda mutação POST/PATCH/PUT/DELETE com hash do body |

## 2. Controles por categoria

### Autenticação
- JWT HS256, access token 15min (default), refresh token rotativo 30d.
- bcrypt para senhas (cost default 12).
- Logout revoga refresh; logout-all revoga todos do sub.

### Autorização
- `current_user` dependency em todos os endpoints de negócio.
- Em produção, **anonymous é bloqueado**.
- Multi-tenancy: `org_id` no JWT (item 16). RLS Supabase pendente (item futuro).

### Transporte
- HSTS preload em produção.
- Cookies `Secure` + `SameSite=strict`.
- CORS por origin explícito.

### Dados sensíveis
- Senhas: bcrypt nunca em plaintext.
- SERPRO: hash sha256 com pepper `ORGCONC_SERPRO_AUDIT_SALT` nos logs.
- Refresh tokens: apenas sha256 hex armazenado (token plain só no cookie do cliente).
- Anthropic key: lida só de env, masking no `/health`.

### Disponibilidade
- Rate-limit distribuído (Redis) por `sub` ou IP.
- Health check com circuit breaker implícito (timeout 3s por dep).
- Pool DB com `pool_pre_ping`.

### Auditoria & forense
- Request-ID em todo log + response header.
- `audit_log`: org_id + sub + ação + entidade + payload_hash + ip + ua + status + criado_em.
- Sentry: stacktraces sem PII (mask antes do send).

## 3. Reporte de vulnerabilidade

Encontrou algo? **Não abra issue público.**

Email: orgatec.cloud@gmail.com com assunto `[SECURITY] <descrição curta>`.

Esperamos:
1. Descrição reproduzível
2. Impacto estimado (confidencialidade/integridade/disponibilidade)
3. Sugestão de mitigação (opcional)

Resposta:
- **24h**: ack
- **7d**: triagem + plano
- **30d**: fix ou explicação se não-vulnerável

## 4. Rotação de segredos

| Segredo | Periodicidade | Procedimento |
|---|---|---|
| `ORGCONC_JWT_SECRET` | Trimestral | Gera novo; invalida todos os tokens (force relogin) |
| `ORGCONC_ADMIN_SENHA_HASH` | Anual ou compromisso | `POST /auth/hash`; trocar env |
| `ANTHROPIC_API_KEY` | Sob compromisso | Rotate na Anthropic Console; trocar env |
| `DATABASE_URL` (senha) | Semestral | Trocar no Supabase; trocar env |
| `ORGCONC_SERPRO_AUDIT_SALT` | **Nunca** | Trocar quebra auditoria forense histórica |
| `S3_*` keys | Trimestral | Rotate no provider |

## 5. Compliance

- **LGPD**: PII em logs sempre mascarada; audit log permite responder DSAR.
- **MP 2.200-2 (cert digital BR)**: SERPRO mTLS quando contrato exigir.
- **Backup**: Supabase Pro point-in-time 7d.

## 6. Threat hunting

Queries úteis no SIEM (futuro):

```sql
-- Logins falhos repetidos por IP
SELECT ip, COUNT(*) FROM audit_log
WHERE acao='action' AND entidade='Auth' AND status_code=401
  AND criado_em > now() - INTERVAL '10 minutes'
GROUP BY ip HAVING COUNT(*) >= 5;

-- Refresh tokens revogados (anti-replay disparou)
SELECT * FROM refresh_tokens
WHERE revogado_em IS NOT NULL
  AND substituido_por IS NULL  -- revogados sem rotacao = forcado por logout/api
ORDER BY revogado_em DESC LIMIT 50;
```
