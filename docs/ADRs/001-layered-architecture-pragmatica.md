# ADR-001: Arquitetura em camadas pragmática (não Clean Architecture pura)

- **Status:** Aceito
- **Data:** 2026-05-25
- **Decisor:** Time OrgConc

## Contexto

Em maio de 2026, o OrgConc tinha:
- Lógica de negócio nos routers (`conciliacao.py` com 257 linhas, 10 passos).
- Sem padrão Repository (CRUD em funções módulo).
- Domínio implícito (entidades = `dict`, regras em `parsers/`).

Opções para reorganizar:
1. **Clean Architecture pura** (Entities, Use Cases, Interface Adapters, Frameworks).
2. **Hexagonal/Ports & Adapters** estrito.
3. **Layered pragmática** (Presentation → Application → Domain → Infrastructure).

## Decisão

Adotamos **Layered pragmática**, com as seguintes regras:
- Domínio em `api/domain/` não importa nada externo.
- Use cases em `api/usecases/` orquestram domínio + interfaces.
- Infra em `api/infra/` implementa Protocols declarados no domínio.
- Routers magros (≤ 30 linhas) delegam ao use case.
- DI centralizada em `api/wiring.py`.

Não adotamos:
- Entity ↔ ORM model totalmente separados (toleramos SQLAlchemy model fazer dupla função no curto prazo via mappers no Repository).
- Hexagonal estrito com "ports" como interfaces nomeadas além de Protocols.

## Consequências

**Positivas:**
- Testabilidade alta no domínio (mockar interfaces).
- Onboarding mais rápido que Clean pura.
- Migração incremental — funções legadas continuam expostas via facade.

**Negativas:**
- Acoplamento residual: alguns routers ainda chamam services direto (Conciliação OFX). Refactor pendente.
- Dupla representação (Entity ↔ ORM) gera mapeamento manual.

## Alternativas rejeitadas

- **Clean pura**: excesso de boilerplate para equipe de 1-2 devs.
- **Hexagonal estrito**: ports + adapters explícitos só agregaria valor com 5+ devs.
