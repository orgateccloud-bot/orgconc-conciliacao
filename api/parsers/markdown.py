"""Parser de Markdown / TXT.

Estrategia:
1. Se houver tabela pipe (`| data | valor | descricao |`), parsea linha a linha.
2. Senao, devolve UMA transacao com o texto bruto no memo —
   o LLM (Claude) processa o conteudo textual diretamente.

Isso permite usuario colar relatorios em prosa, listas, ou tabelas markdown.
"""
from __future__ import annotations

import re
from datetime import datetime


_DATE_PATTERNS = [
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),                       # 2026-04-15
    re.compile(r"(\d{2})/(\d{2})/(\d{4})"),                       # 15/04/2026
    re.compile(r"(\d{2})-(\d{2})-(\d{4})"),                       # 15-04-2026
]
_VALOR_RE = re.compile(
    r"(-?\s*R?\$?\s*[\d.]+,\d{2}|-?\s*\d+(?:\.\d+)?)"
)


def _parse_data(s: str) -> str:
    s = s.strip()
    for rx in _DATE_PATTERNS:
        m = rx.search(s)
        if not m:
            continue
        g = m.groups()
        if len(g[0]) == 4:        # YYYY-MM-DD
            return f"{g[0]}-{g[1]}-{g[2]}"
        # DD?M?YYYY -> YYYY-MM-DD
        return f"{g[2]}-{g[1]}-{g[0]}"
    # Fallback: hoje
    return datetime.utcnow().strftime("%Y-%m-%d")


def _parse_valor(s: str) -> float:
    """Aceita 'R$ 1.234,56', '-1.234,56', '1234.56', etc."""
    s = s.strip()
    # Caso BR: 1.234,56 ou -1.234,56
    if "," in s and re.search(r",\d{2}$", s):
        s = s.replace(".", "").replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s) if s and s not in ("-", ".") else 0.0
    except ValueError:
        return 0.0


def _parsear_tabela_pipe(text: str, conta: str) -> list[dict]:
    """Detecta blocos `| col | col | col |` e extrai transacoes.

    Espera colunas em qualquer ordem contendo 'data', 'valor', 'descr|memo|hist'.
    Linhas de separador (`|---|---|`) sao ignoradas.
    """
    transacoes: list[dict] = []
    linhas = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(linhas) < 3:           # header + sep + ao menos 1 linha
        return transacoes

    header = [c.strip().lower() for c in linhas[0].strip("|").split("|")]

    def col_index(*keywords: str) -> int | None:
        for i, h in enumerate(header):
            if any(k in h for k in keywords):
                return i
        return None

    idx_data  = col_index("data", "dt", "date")
    idx_valor = col_index("valor", "vlr", "amount", "montante")
    idx_memo  = col_index("desc", "memo", "histor", "lancamento", "detalhe")
    idx_tipo  = col_index("tipo", "trntype", "natureza")

    if idx_data is None or idx_valor is None:
        return transacoes

    # Pula header e separator (segunda linha eh sempre |---|---|...|)
    for ln in linhas[2:]:
        cols = [c.strip() for c in ln.strip("|").split("|")]
        if len(cols) <= max(idx_data, idx_valor):
            continue
        try:
            valor = _parse_valor(cols[idx_valor])
        except Exception:
            continue
        if valor == 0.0:
            continue
        transacoes.append({
            "conta":    conta,
            "data":     _parse_data(cols[idx_data]),
            "tipo":     cols[idx_tipo] if idx_tipo is not None and idx_tipo < len(cols) else ("CREDIT" if valor > 0 else "DEBIT"),
            "valor":    valor,
            "memo":     cols[idx_memo] if idx_memo is not None and idx_memo < len(cols) else "",
            "nome":     "",
            "checknum": "",
        })
    return transacoes


def _parse_md(text: str, filename: str) -> list[dict]:
    """Roteia: tabela pipe se houver, senao 1 transacao placeholder com texto bruto."""
    conta = f"MD ({filename})"

    transacoes = _parsear_tabela_pipe(text, conta)
    if transacoes:
        return transacoes

    # Fallback: 1 transacao "container" com texto completo no memo.
    # O LLM Claude processa o markdown bruto e extrai informacoes.
    return [{
        "conta":    conta,
        "data":     datetime.utcnow().strftime("%Y-%m-%d"),
        "tipo":     "MEMO",
        "valor":    0.0,
        "memo":     text[:8000],   # limite defensivo
        "nome":     filename,
        "checknum": "",
    }]
