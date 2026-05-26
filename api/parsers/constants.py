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
