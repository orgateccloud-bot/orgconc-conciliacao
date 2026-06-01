"""Constantes compartilhadas entre os parsers de extrato bancario."""
from __future__ import annotations

# Palavras-chave que identificam transferencias entre contas proprias
_KEYWORDS_TRANSF: tuple[str, ...] = (
    "INTERCREDIS",
    "TRANSF.CONTAS",
    "TRANSF MESMA TIT",
    "TRANSFERENCIA ENTRE CONTAS",
    "TRANSF ENTRE CONTAS",
    "TRANSFERENCIA PROPRIA",
    "TRF PROPRIA",
)

# Tipos de guia tributaria brasileira (codigos de arrecadacao) — FONTE UNICA.
# Usado pelo roteamento do matcher (api/matchers/cascata) e pela classificacao
# forense (api/matchers/forensics). Antes era duplicado identico nos dois.
# (Obs.: a classificacao CONTABIL em api/parsers/classifier usa uma lista mais
# ampla — RFB/INSS/IRRF/ICMS/etc. — de proposito; nao deriva desta.)
GUIA_TRIBUTO_TIPOS: tuple[str, ...] = (
    "DARF",   # Receita Federal
    "DAS",    # Simples Nacional
    "GPS",    # Previdencia (INSS)
    "GNRE",   # ICMS interestadual
    "DAE",    # tributos estaduais
    "DARJ",   # Rio de Janeiro
)

# Limiares de valor para anomalias
LIMITE_VALOR_ALTO: float = 10_000
LIMITE_VALOR_CRITICO: float = 50_000

# Palavras-chave que identificam estornos / reversoes
PALAVRAS_ESTORNO: tuple[str, ...] = (
    "ESTORNO",
    "DEVOL PIX",
    "REJEICAO PIX",
    "DEVOL. PIX",
    "RET PAGTO",
    "CANCEL TED",
    "DEVOLUCAO",
)
