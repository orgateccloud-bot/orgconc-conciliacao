from __future__ import annotations

import re
from collections import defaultdict

from api.parsers.classifier import _classificar


def _top_categorias_e_contrapartes(extratos: list[dict]) -> dict:
    """Retorna estatisticas: categorias, top contrapartes, evolucao diaria."""
    cats: dict[str, dict] = defaultdict(lambda: {"qtd": 0, "valor": 0.0, "transacoes": []})
    contrapartes: dict[str, dict] = defaultdict(lambda: {"qtd": 0, "valor": 0.0})
    diario: dict[str, dict] = defaultdict(lambda: {"cred": 0.0, "deb": 0.0})

    rx_cnpj = re.compile(r"(\d{2}\.\d{3}\.\d{3}[/ ]?\d{4}[- ]?\d{2})")
    rx_cpf = re.compile(r"(\*{3}\.\d{3}\.\d{3}-\*{2})")

    for e in extratos:
        for t in e["transacoes"]:
            c = _classificar(t["memo"], t["nome"])
            cats[c]["qtd"] += 1
            cats[c]["valor"] += t["valor"]
            cats[c]["transacoes"].append(t)

            texto = f"{t['memo']} {t['nome']}"
            m_cnpj = rx_cnpj.search(texto)
            m_cpf = rx_cpf.search(texto)
            chave = None
            if m_cnpj:
                chave = m_cnpj.group(1).strip()
            elif m_cpf:
                chave = m_cpf.group(1).strip()
            elif t["nome"]:
                chave = t["nome"][:30].strip()
            if chave:
                contrapartes[chave]["qtd"] += 1
                contrapartes[chave]["valor"] += t["valor"]

            if t["valor"] > 0:
                diario[t["data"]]["cred"] += t["valor"]
            else:
                diario[t["data"]]["deb"] += t["valor"]

    return {"cats": dict(cats), "contrapartes": dict(contrapartes), "diario": dict(diario)}


# ── CSV helper para prompts LLM ──────────────────────────────────────────────

def _fmt_csv(transacoes: list[dict]) -> str:
    """Formata transacoes como CSV compacto para enviar ao LLM."""
    linhas = ["data,tipo,valor,memo,nome,checknum"]
    for t in transacoes:
        memo = t["memo"].replace(",", " ").replace("\n", " ")
        nome = t["nome"].replace(",", " ").replace("\n", " ")
        linhas.append(
            f"{t['data']},{t['tipo']},{t['valor']:.2f},{memo},{nome},{t['checknum']}"
        )
    return "\n".join(linhas)
