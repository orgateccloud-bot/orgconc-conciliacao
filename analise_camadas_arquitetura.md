# Análise de Camadas de Arquitetura

**Projeto novo (roadmap ideal) vs ORGATEC IA / OrgAudi (estado atual)**

Autor: Warley Veloso — ORGATEC.IA
Data: Maio de 2026
Stack de referência: FastAPI + PostgreSQL + SQLAlchemy + PydanticAI + React/Next.js + Claude API

\---

## Sumário executivo

Este documento compara, camada por camada, como um projeto deveria ser construído do zero contra o estado atual do OrgAudi v8.0.0. O objetivo não é elogiar o que existe — é expor onde o sistema está exposto a risco real, especialmente em um domínio que toca dados fiscais brasileiros e compliance LGPD.

Veredito direto: o OrgAudi tem fundação funcional de aplicação (API, agents, lógica fiscal) mas está fraco exatamente nas camadas que evitam desastre — CI/CD, segurança multi-tenant validada, observabilidade e recuperação de falhas. Essas não são camadas "de polimento". Em um sistema de auditoria fiscal, elas são a diferença entre um produto auditável e um passivo legal.

\---

## Tabela de maturidade por camada

|#|Camada|Projeto novo (alvo)|OrgAudi hoje (estimado)|Gap|Risco|
|-|-|-|-|-|-|
|1|Data \& Persistence|Schema versionado, RLS testada, backup|Schema existe, RLS não validada, backup incerto|Alto|Crítico|
|2|ORM \& Migrations|Models limpos, Alembic, índices|Models OK, migrations parciais|Médio|Médio|
|3|Business Logic|Funções puras, 100% testadas|Lógica fiscal rica, cobertura desconhecida|Alto|Alto|
|4|Multi-Agent|Orquestração testada, fallback|A-00 a A-27 em desenvolvimento|Médio|Médio|
|5|API Gateway|Endpoints versionados, validados|FastAPI funcional, testes parciais|Médio|Médio|
|6|Middleware|Auth + rate limit + error tracking|Mínimo / ausente|Alto|Crítico|
|7|External APIs|Retry, circuit breaker, caching|Claude API + SEFAZ, sem resiliência clara|Alto|Alto|
|8|Frontend|Componentes, state, error boundaries|React/Next.js, terminal-style UI|Baixo|Baixo|
|9|CI/CD \& Deploy|Pipeline verde, deploy automático|Pipeline quebrado (PR #13)|Alto|Crítico|

Os percentuais de "OrgAudi hoje" são estimativas baseadas no contexto disponível, não medições. O primeiro passo de qualquer plano sério é substituir essas estimativas por números reais — rodar `pytest --cov`, testar um restore de backup, tentar furar a própria RLS.

\---

## Camada 1 — Data \& Persistence

### Projeto novo (como fazer certo)

A camada de dados é o alicerce. Tudo acima depende dela e nada acima conserta um erro cometido aqui. As três decisões que importam: schema versionado, Row-Level Security desde o primeiro dia, e backup testado (não apenas configurado).

```yaml
# docker-compose.yml — ambiente local reproduzível
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES\\\_DB: orgatec
      POSTGRES\\\_USER: orgatec\\\_app
      POSTGRES\\\_PASSWORD: ${DB\\\_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: \\\["CMD-SHELL", "pg\\\_isready -U orgatec\\\_app"]
      interval: 10s
      retries: 5

volumes:
  pgdata:
```

Row-Level Security em PostgreSQL é a linha de defesa que garante que dados de uma empresa nunca vazem para outra — mesmo que a query da aplicação tenha um bug:

```sql
-- Habilitar RLS na tabela de auditorias
ALTER TABLE auditorias ENABLE ROW LEVEL SECURITY;

-- Política: usuário só vê auditorias da própria empresa
CREATE POLICY tenant\\\_isolation ON auditorias
  USING (empresa\\\_id = current\\\_setting('app.current\\\_empresa\\\_id')::int);

-- A aplicação define o contexto a cada request:
-- SET app.current\\\_empresa\\\_id = '42';
```

O ponto não óbvio: RLS só protege se a aplicação **sempre** define `app.current\\\_empresa\\\_id` e **nunca** se conecta como superusuário. Um único endpoint que esquece de setar o contexto fura o isolamento inteiro. Por isso isso precisa estar num middleware central, não espalhado pelos endpoints.

### OrgAudi hoje

O modelo `PerfilEmpresa` com 14 setores econômicos e o registro `ClienteReferencia` indicam que a arquitetura multi-tenant foi pensada. O que não está claro é se a RLS está **ativada no banco** ou se o isolamento depende apenas de `WHERE empresa\\\_id = ?` no código da aplicação.

Essa distinção é decisiva. Isolamento só na aplicação significa que um bug em uma query, um endpoint novo sem o filtro, ou uma migração mal feita expõe dados de um produtor rural para outro. Em dados fiscais isso é incidente de LGPD.

### Ação recomendada

Antes de qualquer outra coisa nesta camada: escrever um teste que faz login como usuário da empresa A e tenta — por ID direto — acessar uma auditoria da empresa B. Se a resposta não for 403 ou 404, a RLS não está funcionando, independentemente do que o código aparenta fazer.

\---

## Camada 2 — ORM \& Migrations

### Projeto novo

Models limpos com constraints explícitas e migrations versionadas via Alembic. A regra: nenhuma alteração de schema feita à mão direto no banco — toda mudança é uma migration commitada.

```python
# app/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship, declarative\\\_base

Base = declarative\\\_base()

class Empresa(Base):
    \\\_\\\_tablename\\\_\\\_ = "empresas"
    id = Column(Integer, primary\\\_key=True)
    cnpj = Column(String(14), unique=True, nullable=False, index=True)
    nome = Column(String(255), nullable=False)
    setor\\\_economico = Column(String(50), nullable=False)

class Auditoria(Base):
    \\\_\\\_tablename\\\_\\\_ = "auditorias"
    id = Column(Integer, primary\\\_key=True)
    empresa\\\_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    descricao = Column(String, nullable=False)
    severidade = Column(String(10), nullable=False)
    criado\\\_em = Column(DateTime, server\\\_default=func.now())
    empresa = relationship("Empresa", back\\\_populates="auditorias")
```

O índice em `empresa\\\_id` não é opcional: é a coluna usada em todo filtro multi-tenant. Sem ele, cada listagem vira um sequential scan que degrada conforme o volume cresce.

### OrgAudi hoje

Os models existem e o `\\\_base.py` compartilhado indica boa estrutura. O risco está em migrations parciais — se parte do schema foi criada à mão e parte via Alembic, o ambiente de produção e o de desenvolvimento divergem silenciosamente, e isso só aparece quando um deploy quebra.

### Ação recomendada

Rodar `alembic check` e confirmar que o estado das migrations bate com os models. Consolidar qualquer alteração manual em migration formal.

\---

## Camada 3 — Business Logic

### Projeto novo

A lógica de negócio deve viver em funções puras — sem dependência de banco ou de rede — porque funções puras são triviais de testar e o teste roda em milissegundos.

```python
# app/core/fiscal.py
from dataclasses import dataclass

@dataclass
class Classificacao:
    tipo: str       # F1, F2, F6
    regime: str     # receita, transito, despesa

def classificar\\\_nfe(tipo\\\_operacao: str) -> Classificacao:
    """Regra-mãe de classificação NFA-e."""
    regras = {
        "VENDA":        Classificacao("F1", "receita"),
        "REMESSA":      Classificacao("F2", "transito"),
        "LEILAO":       Classificacao("F2", "transito"),
        "DESTINATARIO": Classificacao("F6", "despesa"),
    }
    if tipo\\\_operacao not in regras:
        raise ValueError(f"Tipo de operação desconhecido: {tipo\\\_operacao}")
    return regras\\\[tipo\\\_operacao]

def calcular\\\_funrural(receita\\\_bruta: float, aliquota: float = 0.023) -> float:
    """Funrural sobre receita bruta da comercialização."""
    if receita\\\_bruta < 0:
        raise ValueError("Receita bruta não pode ser negativa")
    return round(receita\\\_bruta \\\* aliquota, 2)
```

E o teste correspondente — note que ele cobre o caminho de erro, não só o caminho feliz:

```python
# tests/unit/test\\\_fiscal.py
import pytest
from app.core.fiscal import classificar\\\_nfe, calcular\\\_funrural

@pytest.mark.parametrize("tipo,esperado", \\\[
    ("VENDA", "F1"), ("REMESSA", "F2"),
    ("LEILAO", "F2"), ("DESTINATARIO", "F6"),
])
def test\\\_classificacao\\\_correta(tipo, esperado):
    assert classificar\\\_nfe(tipo).tipo == esperado

def test\\\_tipo\\\_invalido\\\_levanta\\\_erro():
    with pytest.raises(ValueError, match="desconhecido"):
        classificar\\\_nfe("TIPO\\\_INEXISTENTE")

def test\\\_funrural\\\_negativo\\\_rejeitado():
    with pytest.raises(ValueError):
        calcular\\\_funrural(-1000)
```

### OrgAudi hoje

Aqui o OrgAudi é provavelmente mais forte que um projeto novo: a regra-mãe, o cálculo de Funrural e IRPF Rural, e o catálogo de anomalias AN-01 a AN-18 representam lógica de domínio madura, validada em auditorias reais. O SKILL\_RURAL.yaml de 730 linhas é um ativo sério.

O risco não está na lógica em si — está na ausência de uma rede de testes em torno dela. Um sistema com lógica fiscal complexa e zero cobertura de regressão é um sistema onde qualquer refatoração pode reintroduzir, sem aviso, o erro de classificação de DESTINATÁRIO que já foi corrigido uma vez.

### Ação recomendada

Estabelecer baseline real de cobertura com `pytest --cov`. Priorizar testes nas funções de classificação e cálculo — são as que, se quebrarem, produzem laudos errados.

\---

## Camada 4 — Multi-Agent System

### Projeto novo

Orquestração de agentes com PydanticAI exige que cada agente tenha entrada e saída tipadas, e que o orquestrador tenha um caminho de fallback quando um agente falha.

```python
# app/agents/orquestrador.py
from pydantic import BaseModel
from pydantic\\\_ai import Agent

class ResultadoAuditoria(BaseModel):
    classificacao: str
    anomalias: list\\\[str]
    confianca: float

agente\\\_fiscal = Agent(
    "claude-sonnet-4-6",
    result\\\_type=ResultadoAuditoria,
    system\\\_prompt="Você é um auditor fiscal especializado em NFA-e rural.",
)

async def executar\\\_com\\\_fallback(documento: str) -> ResultadoAuditoria:
    try:
        resultado = await agente\\\_fiscal.run(documento)
        return resultado.data
    except Exception as e:
        # Falha do agente não pode derrubar o pipeline inteiro
        return ResultadoAuditoria(
            classificacao="INDETERMINADO",
            anomalias=\\\[f"erro\\\_processamento: {type(e).\\\_\\\_name\\\_\\\_}"],
            confianca=0.0,
        )
```

### OrgAudi hoje

O sistema A-00 a A-27 com pipeline NFA-e é a camada mais distintiva do projeto. A pergunta de risco é: o que acontece quando a Claude API está indisponível ou retorna erro no meio de um lote de 17 laudos? Se a resposta for "o lote inteiro falha", a camada precisa de tratamento de falha por agente.

### Ação recomendada

Garantir que falha de um agente seja isolada — registrada, marcada como indeterminada — sem abortar o pipeline. Combinar com o Batch API (PR #30) para reduzir custo e exposição a rate limits.

\---

## Camada 5 — API Gateway

### Projeto novo

Endpoints com validação Pydantic na entrada e na saída, versionados, e com testes de integração que cobrem autenticação e casos de erro.

```python
# app/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1")

class AuditoriaCreate(BaseModel):
    empresa\\\_id: int
    descricao: str = Field(min\\\_length=1, max\\\_length=2000)
    severidade: str = Field(pattern="^(BAIXO|MEDIO|ALTO)$")

@router.post("/auditorias", status\\\_code=201)
async def criar\\\_auditoria(
    payload: AuditoriaCreate,
    usuario=Depends(get\\\_current\\\_user),
):
    if payload.empresa\\\_id != usuario.empresa\\\_id:
        raise HTTPException(403, "Empresa não autorizada")
    # ... persistência
```

### OrgAudi hoje

FastAPI funcional com endpoints para o pipeline de auditoria. O gap é cobertura de testes de integração — sem eles, uma mudança num endpoint pode quebrar produção sem que ninguém perceba até um cliente reclamar.

### Ação recomendada

Cobrir cada endpoint com pelo menos três testes: caminho feliz, requisição sem autenticação (espera 401), e payload inválido (espera 422).

\---

## Camada 6 — Middleware

### Projeto novo

Middleware concentra preocupações transversais: validação de token, injeção do contexto multi-tenant, rate limiting e captura de erro. Centralizar aqui é o que garante que nenhum endpoint esqueça uma dessas etapas.

```python
# app/middleware/tenant.py
from starlette.middleware.base import BaseHTTPMiddleware

class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call\\\_next):
        usuario = await autenticar(request)
        if usuario:
            # Define o contexto que a RLS do PostgreSQL usa
            request.state.empresa\\\_id = usuario.empresa\\\_id
        return await call\\\_next(request)
```

### OrgAudi hoje

Esta é, junto com CI/CD, a camada mais fraca. Sem middleware de erro centralizado (Sentry ou equivalente), o sistema fica cego: quando algo quebra em produção, não há registro estruturado de onde nem por quê. Sem rate limiting, um pico de uso pode esgotar os créditos da Claude API — o que conecta diretamente ao problema de billing já identificado nas prioridades.

### Ação recomendada

Implementar, nesta ordem: middleware de contexto multi-tenant (sustenta a RLS da Camada 1), captura de erro com Sentry, e rate limiting via Redis.

\---

## Camada 7 — External APIs

### Projeto novo

Toda chamada a serviço externo — Claude API, SEFAZ-GO — precisa de retry com backoff exponencial e, idealmente, circuit breaker. Serviços externos falham; o sistema não pode falhar junto.

```python
# app/integrations/claude.py
import asyncio

async def chamar\\\_com\\\_retry(func, max\\\_tentativas=3):
    for tentativa in range(max\\\_tentativas):
        try:
            return await func()
        except Exception:
            if tentativa == max\\\_tentativas - 1:
                raise
            await asyncio.sleep(2 \\\*\\\* tentativa)  # 1s, 2s, 4s
```

### OrgAudi hoje

A integração com Claude API e SEFAZ-GO existe. O trabalho de cost modeling (prompt caching, Batch API, roteamento Haiku/Sonnet) é maduro. O gap é resiliência: o que acontece quando a SEFAZ está fora do ar no meio de uma auditoria.

### Ação recomendada

Adicionar retry com backoff em todas as chamadas externas. Para a Claude API, combinar com o LRU cache do PR #30.

\---

## Camada 8 — Frontend

### Projeto novo

Componentes React com error boundaries para que uma falha em um componente não derrube a página inteira.

```jsx
class ErrorBoundary extends React.Component {
  state = { erro: false };
  static getDerivedStateFromError() { return { erro: true }; }
  render() {
    if (this.state.erro) return <p>Algo deu errado ao carregar este painel.</p>;
    return this.props.children;
  }
}
```

### OrgAudi hoje

A camada de menor risco. A UI com estética "private bank meets Bloomberg terminal", tipografia Playfair Display e activity log estilo terminal é diferenciada e bem pensada. O cuidado aqui é apenas garantir error boundaries e performance no log de atividade.

### Ação recomendada

Manutenção. Esta camada não é prioridade frente a Middleware e CI/CD.

\---

## Camada 9 — CI/CD \& Deployment

### Projeto novo

Pipeline que roda testes em cada push e bloqueia merge se algo falhar.

```yaml
# .github/workflows/test.yml
name: Tests
on: \\\[push, pull\\\_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".\\\[dev]"
      - run: pytest --cov=app --cov-report=term-missing
```

### OrgAudi hoje

Pipeline quebrado no PR #13. Esta é a camada mais crítica para resolver, porque um pipeline quebrado significa que **nenhuma das outras camadas tem garantia de qualidade**. Cada merge é uma aposta. Cada melhoria nas Camadas 1 a 8 fica sem rede de proteção.

### Ação recomendada

Prioridade número um. Consertar o PR #13 antes de qualquer trabalho de feature nova. Sem pipeline, todo o resto deste documento é construído sobre areia.

\---

## Plano de execução priorizado

A ordem abaixo não é por facilidade — é por risco. Itens críticos primeiro, mesmo que sejam chatos.

### Semanas 1–4: bloqueadores críticos

1. Consertar o CI/CD (PR #13). Sem isso, nada mais tem garantia.
2. Validar a RLS com um teste de invasão real (login como A, acesso a B).
3. Implementar e testar backup/recovery dos dados SEFAZ-GO.
4. Adicionar error tracking (Sentry) via middleware.

### Semanas 5–8: robustez

5. Estabelecer baseline real de cobertura de testes.
6. Implementar rate limiting (protege a Claude API e o billing).
7. Merge do PR #30 (LRU cache + Batch API).
8. Adicionar retry/backoff nas integrações externas.

### Semanas 9+: otimização

9. Consolidar os três motores de PDF concorrentes em um.
10. Otimização de queries conforme o volume cresce.
11. Refino de custo e roteamento de modelos.

\---

## Conclusão

O OrgAudi não é um projeto frágil — tem lógica de domínio sólida, arquitetura multi-tenant pensada e um sistema de agentes ambicioso. Mas tem um padrão de risco claro: as camadas de funcionalidade estão à frente das camadas de segurança e operação.

Em quase qualquer software isso seria dívida técnica administrável. Em um sistema de auditoria fiscal que processa dados de produtores rurais sob LGPD, as Camadas 6 e 9 — middleware e CI/CD — deixam de ser polimento e passam a ser pré-requisito de operação responsável.

A pergunta honesta para fechar: dos quatro itens críticos das semanas 1–4, quantos você consegue afirmar hoje, com testes na mão, que estão realmente resolvidos? Se a resposta for menos que quatro, esse é o trabalho — antes de qualquer feature nova.

\---

*Documento gerado para revisão técnica. Versione este arquivo no repositório Git do projeto — análise de arquitetura fora do controle de versão fica desatualizada em semanas.*

