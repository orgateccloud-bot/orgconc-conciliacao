from __future__ import annotations

from collections import Counter
from itertools import combinations


def _chave_transacao(conta: str, t: dict) -> tuple[str, str, float, str]:
    """Chave unica para marcar transacao anomala na persistencia."""
    return (conta, t["data"], round(t["valor"], 2), (t.get("memo") or "")[:40])


def _coletar_chaves_anomalas(extratos: list[dict]) -> set[tuple[str, str, float, str]]:
    """Retorna chaves exatas das transacoes sinalizadas pelo detector."""
    chaves: set[tuple[str, str, float, str]] = set()
    _KEYWORDS_TRANSF = ("INTERCREDIS", "TRANSF.CONTAS", "TRANSF MESMA TIT", "TRANSFERENCIA ENTRE CONTAS")

    for e in extratos:
        contagem = Counter(
            (t["data"], round(t["valor"], 2), t["memo"][:40]) for t in e["transacoes"]
        )
        for (data, valor, memo), n in contagem.items():
            if n < 2:
                continue
            for t in e["transacoes"]:
                if t["data"] == data and round(t["valor"], 2) == valor and t["memo"][:40] == memo:
                    chaves.add(_chave_transacao(e["conta"], t))

        for t in e["transacoes"]:
            v = abs(t["valor"])
            if v > 10000:
                chaves.add(_chave_transacao(e["conta"], t))
            s = (t.get("memo", "") + t.get("nome", "")).upper()
            if "ESTORNO" in s:
                chaves.add(_chave_transacao(e["conta"], t))

    if len(extratos) >= 2:
        for c1, c2 in combinations(extratos, 2):
            def _eh_transf(t):
                s = (t["memo"] + t["nome"]).upper()
                return any(k in s for k in _KEYWORDS_TRANSF)

            tx1 = [t for t in c1["transacoes"] if _eh_transf(t)]
            tx2 = [t for t in c2["transacoes"] if _eh_transf(t)]
            usados: set[int] = set()
            for t1 in tx1:
                casou = False
                for j, t2 in enumerate(tx2):
                    if j in usados:
                        continue
                    if abs(abs(t1["valor"]) - abs(t2["valor"])) < 0.01 and t1["valor"] * t2["valor"] < 0:
                        usados.add(j)
                        casou = True
                        break
                if not casou:
                    chaves.add(_chave_transacao(c1["conta"], t1))
            for j, t2 in enumerate(tx2):
                if j not in usados:
                    chaves.add(_chave_transacao(c2["conta"], t2))

    return chaves


def _detectar_anomalias(extratos: list[dict]) -> list[dict]:
    """Identifica anomalias com severidade (critico/alerta/atencao)."""
    anomalias: list[dict] = []

    # Duplicidades
    for e in extratos:
        contagem = Counter(
            (t["data"], round(t["valor"], 2), t["memo"][:40]) for t in e["transacoes"]
        )
        for (data, valor, memo), n in contagem.items():
            if n < 2:
                continue
            sev = "critico" if n >= 3 else "alerta"
            anomalias.append({
                "severidade": sev,
                "tipo": "Duplicidade",
                "titulo": f"{n}x lançamento idêntico em {data}",
                "conta": e["conta"],
                "valor": valor,
                "detalhe": f"R$ {valor:,.2f} | {memo} | {n} ocorrências",
            })

    # Transacoes atipicas
    for e in extratos:
        for t in e["transacoes"]:
            v = abs(t["valor"])
            memo = (t["memo"] or t["nome"])[:60]
            if v > 50000:
                anomalias.append({
                    "severidade": "alerta", "tipo": "Valor alto",
                    "titulo": f"Transação de R$ {v:,.2f}",
                    "conta": e["conta"], "valor": t["valor"],
                    "detalhe": f"{t['data']} | {memo}",
                })
            elif v > 10000:
                anomalias.append({
                    "severidade": "atencao", "tipo": "Valor alto",
                    "titulo": f"Transação de R$ {v:,.2f}",
                    "conta": e["conta"], "valor": t["valor"],
                    "detalhe": f"{t['data']} | {memo}",
                })

    # Estornos
    for e in extratos:
        for t in e["transacoes"]:
            s = (t["memo"] + t["nome"]).upper()
            if "ESTORNO" in s:
                anomalias.append({
                    "severidade": "critico", "tipo": "Estorno",
                    "titulo": "Operação estornada",
                    "conta": e["conta"], "valor": t["valor"],
                    "detalhe": f"{t['data']} | R$ {t['valor']:,.2f} | {t['memo'][:60]}",
                })

    # Transferencias internas sem par
    _KEYWORDS_TRANSF = ("INTERCREDIS", "TRANSF.CONTAS", "TRANSF MESMA TIT", "TRANSFERENCIA ENTRE CONTAS")
    if len(extratos) >= 2:
        for c1, c2 in combinations(extratos, 2):
            def _eh_transf(t):
                s = (t["memo"] + t["nome"]).upper()
                return any(k in s for k in _KEYWORDS_TRANSF)
            tx1 = [t for t in c1["transacoes"] if _eh_transf(t)]
            tx2 = [t for t in c2["transacoes"] if _eh_transf(t)]
            usados: set[int] = set()
            casados = 0
            for t1 in tx1:
                for j, t2 in enumerate(tx2):
                    if j in usados:
                        continue
                    if abs(abs(t1["valor"]) - abs(t2["valor"])) < 0.01 and t1["valor"] * t2["valor"] < 0:
                        usados.add(j); casados += 1; break
            sem_par = (len(tx1) - casados) + (len(tx2) - casados)
            if sem_par > 0:
                anomalias.append({
                    "severidade": "alerta", "tipo": "Transferencia sem par",
                    "titulo": f"{sem_par} transferência(s) interna(s) sem par",
                    "conta": f"{c1['conta']} ↔ {c2['conta']}", "valor": 0,
                    "detalhe": (
                        f"{c1['conta']}: {len(tx1) - casados} sem par | "
                        f"{c2['conta']}: {len(tx2) - casados} sem par"
                    ),
                })

    ordem = {"critico": 0, "alerta": 1, "atencao": 2}
    anomalias.sort(key=lambda a: (ordem[a["severidade"]], -abs(a.get("valor", 0))))
    return anomalias
