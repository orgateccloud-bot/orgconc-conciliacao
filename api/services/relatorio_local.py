"""Gerador deterministico de relatorio de conciliacao em Markdown (sem LLM).

Funcao publica: _conciliacao_local(extratos, anomalias) -> str
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from itertools import combinations as _combis

from api.parsers import _classificar, _top_categorias_e_contrapartes


def _conciliacao_local(extratos: list[dict], anomalias: list[dict]) -> str:
    """Gera relatorio de conciliacao deterministicamente (sem LLM) — versao enriquecida."""
    out = ["# Relatório de Conciliação Bancária\n"]
    out.append(f"**Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M')}  \n")
    out.append(f"**Modo:** Simulação local (sem LLM)  \n")
    out.append(f"**Extratos analisados:** {len(extratos)}\n\n")

    stats = _top_categorias_e_contrapartes(extratos)

    crit = [a for a in anomalias if a["severidade"] == "critico"]
    alerta = [a for a in anomalias if a["severidade"] == "alerta"]
    atencao = [a for a in anomalias if a["severidade"] == "atencao"]
    out.append("## ⚠️ Achados de Anomalias\n\n")
    out.append(f"- 🔴 **Críticos:** {len(crit)}\n")
    out.append(f"- 🟠 **Alertas:** {len(alerta)}\n")
    out.append(f"- 🟡 **Atenção:** {len(atencao)}\n\n")
    if crit:
        out.append("### 🔴 Críticos\n\n")
        for a in crit:
            out.append(f"- **[{a['tipo']}]** {a['titulo']} — {a['conta']}\n  {a['detalhe']}\n")
        out.append("\n")
    if alerta:
        out.append("### 🟠 Alertas\n\n")
        for a in alerta[:15]:
            out.append(f"- **[{a['tipo']}]** {a['titulo']} — {a['conta']}\n  {a['detalhe']}\n")
        if len(alerta) > 15:
            out.append(f"- _...e mais {len(alerta) - 15} alerta(s)_\n")
        out.append("\n")

    # === 1. RESUMO EXECUTIVO ===
    out.append("## 1. Resumo Executivo\n\n")
    total_tx = sum(e["qtd"] for e in extratos)
    total_cred = sum(t["valor"] for e in extratos for t in e["transacoes"] if t["valor"] > 0)
    total_deb = sum(t["valor"] for e in extratos for t in e["transacoes"] if t["valor"] < 0)
    total_liq = total_cred + total_deb
    ticket_medio = (total_cred + abs(total_deb)) / max(total_tx, 1)
    datas = sorted({t["data"] for e in extratos for t in e["transacoes"] if t["data"]})
    periodo = f"{datas[0]} a {datas[-1]}" if datas else "indefinido"
    out.append(f"**Período analisado:** {periodo}  \n")
    out.append(f"**Total de transações:** {total_tx}  \n")
    out.append(f"**Ticket médio:** R$ {ticket_medio:,.2f}  \n")
    out.append(f"**Volume bruto movimentado:** R$ {total_cred + abs(total_deb):,.2f}\n\n")

    out.append("| Conta | Transações | Créditos | Débitos | Saldo Líquido | % Volume |\n")
    out.append("|---|---:|---:|---:|---:|---:|\n")
    vol_total = total_cred + abs(total_deb)
    for e in extratos:
        cred = sum(t["valor"] for t in e["transacoes"] if t["valor"] > 0)
        deb = sum(t["valor"] for t in e["transacoes"] if t["valor"] < 0)
        liq = cred + deb
        vol_e = cred + abs(deb)
        pct = (vol_e / vol_total * 100) if vol_total else 0
        out.append(
            f"| {e['conta']} | {e['qtd']} | R$ {cred:,.2f} | R$ {deb:,.2f} | "
            f"**R$ {liq:,.2f}** | {pct:.1f}% |\n"
        )
    out.append(f"| **CONSOLIDADO** | **{total_tx}** | **R$ {total_cred:,.2f}** | "
               f"**R$ {total_deb:,.2f}** | **R$ {total_liq:,.2f}** | 100,0% |\n\n")

    # === 2. INDICADORES OPERACIONAIS ===
    out.append("## 2. Indicadores Operacionais\n\n")
    sev_count = {"critico": len(crit), "alerta": len(alerta), "atencao": len(atencao)}
    saude = "🟢 Boa" if sev_count["critico"] == 0 else (
        "🟡 Atenção" if sev_count["critico"] <= 2 else "🔴 Crítica"
    )
    n_dias = len(datas) or 1
    media_diaria_tx = total_tx / n_dias
    cats_count = sum(1 for k in stats["cats"] if k != "A classificar")
    pct_classif = (
        (sum(d["qtd"] for k, d in stats["cats"].items() if k != "A classificar") / total_tx * 100)
        if total_tx else 0
    )
    out.append("| Indicador | Valor |\n|---|---:|\n")
    out.append(f"| Saúde da conciliação | {saude} |\n")
    out.append(f"| Dias com movimento | {n_dias} |\n")
    out.append(f"| Média de transações/dia | {media_diaria_tx:.1f} |\n")
    out.append(f"| Categorias contábeis detectadas | {cats_count} |\n")
    out.append(f"| Cobertura de classificação | {pct_classif:.1f}% |\n")
    out.append(f"| Total de anomalias | {len(anomalias)} ({sev_count['critico']} críticas) |\n\n")

    # === 3. TRANSFERENCIAS ENTRE CONTAS ===
    out.append("## 3. Transferências entre Contas Próprias\n\n")
    _KEYWORDS_TRANSF = ("INTERCREDIS", "TRANSF.CONTAS", "TRANSF MESMA TIT", "TRANSFERENCIA ENTRE CONTAS")

    def _eh_transf(t):
        s = (t["memo"] + t["nome"]).upper()
        return any(k in s for k in _KEYWORDS_TRANSF)

    if len(extratos) >= 2:
        total_pares_encontrados = 0
        total_volume = 0.0
        out.append("| Data | Origem | Destino | Valor | Status |\n|---|---|---|---:|:-:|\n")
        for c1, c2 in _combis(extratos, 2):
            tx1 = [t for t in c1["transacoes"] if _eh_transf(t)]
            tx2 = [t for t in c2["transacoes"] if _eh_transf(t)]
            usados: set[int] = set()
            for t1 in tx1:
                for j, t2 in enumerate(tx2):
                    if j in usados:
                        continue
                    if abs(abs(t1["valor"]) - abs(t2["valor"])) < 0.01 and t1["valor"] * t2["valor"] < 0:
                        origem = c1["conta"] if t1["valor"] < 0 else c2["conta"]
                        destino = c2["conta"] if t1["valor"] < 0 else c1["conta"]
                        v = abs(t1["valor"])
                        out.append(f"| {t1['data']} | {origem} | {destino} | R$ {v:,.2f} | ✅ CASADO |\n")
                        total_volume += v
                        total_pares_encontrados += 1
                        usados.add(j)
                        break
        if total_pares_encontrados:
            out.append(f"\n**Resumo:** {total_pares_encontrados} par(es) conciliado(s) · "
                       f"Volume total R$ {total_volume:,.2f}\n\n")
        else:
            out.append("\n_Nenhuma transferência entre contas detectada._\n\n")
    else:
        out.append("_Apenas 1 extrato enviado — cruzamento entre contas não aplicável._\n\n")

    # === 4. TOP CATEGORIAS CONTÁBEIS ===
    out.append("## 4. Distribuição por Categoria Contábil\n\n")
    cats = stats["cats"]
    out.append("| Categoria | Qtd | Valor Total | Ticket Médio | % do Volume |\n|---|---:|---:|---:|---:|\n")
    for cat in sorted(cats, key=lambda k: -abs(cats[k]["valor"])):
        d = cats[cat]
        tk = d["valor"] / d["qtd"] if d["qtd"] else 0
        pct = (abs(d["valor"]) / vol_total * 100) if vol_total else 0
        out.append(f"| {cat} | {d['qtd']} | R$ {d['valor']:,.2f} | R$ {tk:,.2f} | {pct:.1f}% |\n")
    out.append("\n")

    # === 5. TOP CONTRAPARTES ===
    out.append("## 5. Top Contrapartes (Pareto)\n\n")
    cps = stats["contrapartes"]
    top_cps = sorted(cps.items(), key=lambda x: -abs(x[1]["valor"]))[:12]
    if top_cps:
        out.append("| # | Contraparte | Transações | Volume | Tipo |\n|---:|---|---:|---:|:-:|\n")
        for i, (chave, d) in enumerate(top_cps, 1):
            tipo = "💚 Recebimento" if d["valor"] > 0 else "🔻 Pagamento"
            out.append(f"| {i} | `{chave}` | {d['qtd']} | R$ {d['valor']:,.2f} | {tipo} |\n")
        out.append("\n")
    else:
        out.append("_Sem contrapartes identificáveis por CNPJ/CPF._\n\n")

    # === 6. DUPLICIDADES DETALHADAS ===
    out.append("## 6. Duplicidades Detectadas\n\n")
    achou_dup = False
    for e in extratos:
        contagem = Counter(
            (t["data"], round(t["valor"], 2), t["memo"][:40]) for t in e["transacoes"]
        )
        dups = [k for k, n in contagem.items() if n > 1]
        if dups:
            achou_dup = True
            out.append(f"### {e['conta']}\n\n")
            out.append("| Data | Valor | Memo | Ocorrências | Impacto Total |\n|---|---:|---|:-:|---:|\n")
            for data, valor, memo in sorted(dups, key=lambda k: -contagem[k]):
                n = contagem[(data, valor, memo)]
                impacto = valor * n
                emoji = "🔴" if n >= 3 else "🟠"
                out.append(f"| {data} | R$ {valor:,.2f} | `{memo}` | {emoji} **{n}x** | R$ {impacto:,.2f} |\n")
            out.append("\n")
    if not achou_dup:
        out.append("✅ _Nenhuma duplicidade detectada._\n\n")

    # === 7. TRANSACOES ATIPICAS ===
    out.append("## 7. Transações Atípicas (> R$ 10.000)\n\n")
    atipicas = []
    for e in extratos:
        for t in e["transacoes"]:
            if abs(t["valor"]) > 10000:
                atipicas.append((e["conta"], t))
    if atipicas:
        atipicas.sort(key=lambda x: -abs(x[1]["valor"]))
        out.append("| Conta | Data | Valor | Memo | Classificação |\n|---|---|---:|---|---|\n")
        for conta, t in atipicas[:20]:
            memo = (t["memo"] or t["nome"])[:55]
            cat = _classificar(t["memo"], t["nome"])
            out.append(f"| {conta} | {t['data']} | **R$ {t['valor']:,.2f}** | {memo} | {cat} |\n")
        if len(atipicas) > 20:
            out.append(f"\n_...e mais {len(atipicas) - 20} transação(ões) atípica(s)._\n")
        out.append("\n")
    else:
        out.append("✅ _Nenhuma transação acima de R$ 10.000._\n\n")

    # === 8. EVOLUCAO DIARIA ===
    diario = stats["diario"]
    if len(diario) > 1:
        out.append("## 8. Evolução Diária do Fluxo\n\n")
        out.append("| Data | Créditos | Débitos | Saldo do Dia |\n|---|---:|---:|---:|\n")
        for data in sorted(diario.keys()):
            d = diario[data]
            sld = d["cred"] + d["deb"]
            out.append(f"| {data} | R$ {d['cred']:,.2f} | R$ {d['deb']:,.2f} | R$ {sld:,.2f} |\n")
        out.append("\n")

    # === 9. PLANO DE AÇÃO ===
    out.append("## 9. Plano de Ação Recomendado\n\n")
    if crit:
        out.append("### 🔴 Imediato (24-48h)\n\n")
        for a in crit[:5]:
            out.append(f"1. **{a['titulo']}** — {a['conta']}  \n   _{a['detalhe']}_\n")
        out.append("\n")
    if alerta:
        out.append("### 🟠 Curto prazo (esta semana)\n\n")
        for a in alerta[:5]:
            out.append(f"1. Investigar: **{a['titulo']}** — {a['conta']}\n")
        out.append("\n")

    a_classificar = cats.get("A classificar", {}).get("qtd", 0)
    if a_classificar > 0:
        out.append("### 🟡 Médio prazo\n\n")
        out.append(f"- Classificar manualmente **{a_classificar} transação(ões)** sem regra automática\n")
        out.append("- Refinar regras de classificação para reduzir cobertura abaixo de 100%\n\n")

    out.append("### ✅ Boas práticas\n\n")
    out.append("- Implementar conciliação diária (vs. mensal) para detectar duplicidades cedo\n")
    out.append("- Confirmar comprovantes de PIX acima de R$ 1.000\n")
    out.append("- Revisar estornos com o banco antes do fechamento contábil\n")
    out.append("- Documentar transferências entre contas próprias com referência cruzada\n")

    return "".join(out)
