# ORGATEC · Conciliação Bancária

API e UI web para conciliação bancária inteligente. Cruza extratos OFX/PDF/XML, detecta anomalias, gera relatórios em HTML, XLSX e PDF.

## Stack

- **Backend**: FastAPI + Uvicorn (Python 3.10+)
- **Parsers**: OFX (SGML), PDF (`pdfplumber`), XML (CAMT.053 + OFX-XML)
- **Exports**: Markdown nativo, HTML standalone, XLSX (`openpyxl`), PDF (`html2pdf.js` client-side)
- **LLM**: Anthropic Claude (`claude-sonnet-4-5`) opcional, modo simulação local sempre disponível
- **Auth**: Bearer token opcional · **Rate limit**: `slowapi` · **Persistência**: JSON em disco

## Setup

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis
cp .env.example .env
# editar .env e preencher ANTHROPIC_API_KEY

# 3. Rodar servidor
python -m uvicorn api.main:app --host 127.0.0.1 --port 8765 --reload
```

UI: http://127.0.0.1:8765/ui/ · Docs Swagger: http://127.0.0.1:8765/docs

## Endpoints principais

| Método | Rota | Descrição |
|---|---|---|
| `GET`  | `/health` | Healthcheck + status da chave |
| `POST` | `/conciliar/ofx?simular=true` | Upload 1-2 arquivos (.ofx, .pdf, .xml) → JSON com anomalias + relatório |
| `GET`  | `/export/html/{rid}` | Baixa relatório HTML standalone |
| `GET`  | `/export/xlsx/{rid}` | Baixa planilha Excel (3 abas: Resumo, Transações, Anomalias) |

## Modos de operação

- **Simulação** (`?simular=true`): conciliação **gratuita** com heurísticas locais (regex + classificador). Sem chamada à API.
- **Claude LLM** (default): chama Anthropic Messages API para análise narrativa rica.

## Funcionalidades

- 🔍 **Detecção de anomalias** com 3 severidades (crítico/alerta/atenção)
  - Duplicidades (mesma data + valor + memo)
  - Estornos
  - Transações atípicas (>R$ 10k = atenção, >R$ 50k = alerta)
  - Transferências INTERCREDIS sem par
- 🏷 **Classificador contábil** para 10+ bancos (Sicoob, BB, Itaú, Bradesco, Santander, Caixa, Inter, Nubank, C6)
- 📊 **Relatório executivo** com 10 seções (resumo, KPIs operacionais, top contrapartes, evolução diária, plano de ação)
- 🎨 **UI ORGATEC** com tema escuro e branding personalizado

## Configuração (`.env`)

| Variável | Default | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Obrigatório para modo LLM |
| `ORGCONC_AUTH_TOKEN` | (vazio = aberto) | Bearer token opcional |
| `ORGCONC_CORS_ORIGINS` | `http://127.0.0.1:8765,http://localhost:8765` | CORS allowlist |
| `ORGCONC_MAX_UPLOAD_MB` | `10` | Limite por arquivo |
| `ORGCONC_DATA_DIR` | `./data` | Diretório de persistência |

## Testes

```bash
pytest tests/ -v
```

## Estrutura

```
api/main.py         # FastAPI app, parsers, classifier, exports
static/index.html   # UI single-page
static/logo.png     # Logo ORGATEC
tests/test_api.py   # 14 testes (parsers, endpoints, segurança)
.env.example        # Template de configuração
requirements.txt    # Dependências
```

## Licença

Privado · © ORGATEC Contabilidade e Auditoria
