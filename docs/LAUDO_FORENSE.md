# Laudo Forense Integrado — modelo PRINCIPAL

Relatório forense de **11 abas** (LaudoOrgAudi) gerado a partir de extratos OFX +
enriquecimento cadastral (RFB/BrasilAPI). É o **único** modelo de laudo do projeto —
os geradores antigos (v2/v4/v5, `gerar_relatorio_extratos`, `gerar_xlsx_extratos`)
foram removidos.

## Arquitetura

Um núcleo, dois consumidores:

```
api/services/laudo_forense.py   ← NÚCLEO reusável (sem I/O de arquivo, sem dados de cliente)
   ├─ montar_dados(transacoes)            -> (todos, saldos)   [bucket por mês + saldo corrente]
   ├─ construir_empresa(cnpj, cache)      -> dict EMPRESA      [do cache RFB/BrasilAPI]
   ├─ gerar_laudo_workbook(todos,saldos,cache) -> (Workbook, stats)   [as 11 abas]
   ├─ coletar_dados(pasta,conta,cnpj,...) -> (todos,saldos,cache)     [glob+dedup+enriquecer]
   └─ gerar_md / gerar_html / gerar_pdf
        │
        ├── scripts/relatorio_integrado.py   → CLI (wrapper fino)
        └── api/routers/fiscal.py            → POST /fiscal/laudo
```

## CLI

```bash
python scripts/relatorio_integrado.py \
    --pasta C:\caminho\com\ofx \
    --conta 158083 \
    --empresa-cnpj 05509396000110 \
    --tag meu_laudo \
    --enrich-all
```

| Flag | Default | Descrição |
|---|---|---|
| `--pasta` | (Desktop\locar) | pasta com os `.ofx` |
| `--conta` | "" (todas) | escopa a uma conta (substring do ID, ex: `158083`) |
| `--empresa-cnpj` | "" | CNPJ da entidade auditada (14 dígitos) — preenche a aba Identificação via cache |
| `--tag` | `laudo` | sufixo dos arquivos em `Downloads\RELATORIO_INTEGRADO_<tag>.{xlsx,md,html,pdf}` |
| `--enrich-all` | off | enriquece TODOS os CNPJs nativos (senão top-300) |

## API

```
POST /fiscal/laudo   (multipart)
  empresa_cnpj=<14d>   conta=<substring opcional>   arquivos=<1+ .ofx>
  → 200  application/vnd...spreadsheetml.sheet  (XLSX, 11 abas)
```

Usa o **cache de CNPJ existente** (sem rede em-request). Rode `POST /fiscal/processar`
antes (que dispara o enriquecimento em background) para popular situação/pós-baixa.
A geração é **serializada por lock** (a aba Identificação usa um estado de módulo);
é um relatório pesado de baixa concorrência, então isso é aceitável.

## As 11 abas

1. Capa · 2. Identificação · 3. Resumo Executivo · 4. Transações · 5. Disposições (27 col + Risk Score) ·
6. Risk Heatmap · 7. CNPJs (enriquecidos) · 8. Partes Relacionadas (auto-mov. + mesma titularidade) ·
9. MEIs Teto · 10. Status Tributário (N meses) · 11. Pagamentos Pós-Baixa.

## Validação

Reproduz o laudo-verdade LOCAR (`RELATORIO_INTEGRADO_LOCAR_v3_novo.xlsx`) **ao centavo**:
conta 158083-3, 7.110 transações, heatmap CRÍTICO=18/ALTO=59, pós-baixa 17 / R$ 35.626,89.
Smoke test em `tests/test_laudo_forense.py`.

## Privacidade

O código **não** contém dados de cliente — `EMPRESA` é montado em runtime do CNPJ +
enriquecimento. Os dados de entrada (OFX) e saídas (laudos) **nunca** vão para o git.
