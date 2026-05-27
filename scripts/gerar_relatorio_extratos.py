"""Gera relatório consolidado a partir dos OFXs reais (sessão de análise).

Carrega o cache CNPJ enriquecido (cnpj_cache.json) e adiciona seções:
- Contrapartes enriquecidas com razão social
- Alertas: CNPJs BAIXADOS / INAPTOS
- Top fornecedores por volume pago
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r"C:\OrgConc")
from api.matchers.cascata import classificar, ler_ofx

ARQUIVOS = [
    (r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260514110822 (1).ofx", "JAN/2026", "158083-3"),
    (r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260514110900 (1).ofx", "MAR/2026", "158083-3"),
    (r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260514110917 (1).ofx", "ABR/2026", "158083-3"),
    (r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260514110938 (1).ofx", "MAI/2026", "158083-3"),
    (r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260504172522.ofx", "ABR/2026", "9695-4"),
    (r"C:\Users\Veloso\Downloads\extrato-conta-corrente-ofx-unix_202605_20260504172614.ofx", "ABR/2026", "51785-2"),
]

ESTAGIOS = {0: "TRANSF.INTERNA", 1: "CNPJ/CPF", 2: "NF-e", 3: "TARIFA",
            4: "TRIBUTO", 5: "CONTRATO", 6: "ALIAS/FUZZY"}

STATUS_MAP = {
    0: "Auto (regra)",
    1: "Auto se CNPJ cadastrado",
    2: "Auto se XML disponivel",
    3: "Auto (regra)",
    4: "Auto se guia cadastrada",
    5: "Auto se contrato cadastrado",
    6: "Auto se alias / fuzzy LLM",
}

RX_CNPJ = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}[ /]?\d{4}-?\d{2})\b")
RX_CNPJ_GRUPOS = re.compile(r"(\d{2})[.](\d{3})[.](\d{3})[ /](\d{4})[-](\d{2})")
CACHE_PATH = Path(r"C:\OrgConc\data\cnpj_cache.json")


def carregar_cache_cnpj() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def extrair_cnpj_grupos(t) -> str | None:
    """Extrai CNPJ no formato bancário 'X.X.X X-X' das transações."""
    for fonte in (t.nome or "", t.memo or ""):
        m = RX_CNPJ_GRUPOS.search(fonte)
        if m:
            return "".join(m.groups())
    return None


def main() -> None:
    todos = []
    valor_rec = Counter()
    nome_rec = Counter()
    cnpj_rec = Counter()
    volume_por_cnpj = Counter()   # CNPJ -> volume R$ pago (débitos)
    top_deb, top_cred = [], []

    cache_cnpj = carregar_cache_cnpj()

    for path, mes, conta in ARQUIVOS:
        txs = ler_ofx(path)
        for t in txs:
            res = classificar(t)
            todos.append((mes, conta, t, res))
            if t.valor < 0:
                valor_rec[round(abs(t.valor), 2)] += 1
                nome_simp = (t.nome or t.memo or "")[:40].upper().strip()
                if nome_simp and len(nome_simp) > 5:
                    nome_rec[nome_simp] += 1
                cnpj = extrair_cnpj_grupos(t)
                if cnpj:
                    cnpj_rec[cnpj] += 1
                    volume_por_cnpj[cnpj] += abs(t.valor)
                top_deb.append((t.valor, t, mes, conta))
            else:
                top_cred.append((t.valor, t, mes, conta))

    top_valores = valor_rec.most_common(15)
    top_cnpjs = [(d, c) for d, c in cnpj_rec.most_common(15) if c >= 3]
    top_nomes = [(n, c) for n, c in nome_rec.most_common(20) if c >= 5]
    top_deb.sort(key=lambda x: x[0])
    top_cred.sort(key=lambda x: -x[0])

    totais = Counter(res.estagio for _, _, _, res in todos)
    n_tot = len(todos)
    cred_total = sum(t.valor for _, _, t, _ in todos if t.valor > 0)
    deb_total = sum(t.valor for _, _, t, _ in todos if t.valor < 0)

    lines = [
        "# Analise Consolidada - Extratos 2026",
        "",
        f"**Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "**Sistema:** OrgConc + OrgNeural2 (cascata de 6 estagios)",
        "",
        "## 1. Resumo Executivo",
        "",
        f"- **Total de transacoes processadas:** {n_tot:,}",
        f"- **Volume de creditos:** R$ {cred_total:,.2f}",
        f"- **Volume de debitos:** R$ {deb_total:,.2f}",
        "- **Periodo:** Janeiro a Maio/2026",
        "- **Contas:** 158083-3 (principal), 9695-4, 51785-2 - Sicoob (Banco 756)",
        "",
        "## 2. Distribuicao por Estagio",
        "",
        "| Estagio | Tipo | Qtd | % | Status |",
        "|---|---|---|---|---|",
    ]

    for est in range(7):
        if totais.get(est):
            n = totais[est]
            pct = 100 * n / n_tot
            lines.append(f"| {est} | {ESTAGIOS[est]} | {n:,} | {pct:.1f}% | {STATUS_MAP[est]} |")

    lines += ["", "## 3. Por Mes / Conta", "",
              "| Mes | Conta | Transacoes | Creditos (R$) | Debitos (R$) |",
              "|---|---|---|---|---|"]
    por_mc = defaultdict(lambda: {"n": 0, "cred": 0.0, "deb": 0.0})
    for mes, conta, t, _ in todos:
        k = (mes, conta)
        por_mc[k]["n"] += 1
        if t.valor > 0:
            por_mc[k]["cred"] += t.valor
        else:
            por_mc[k]["deb"] += t.valor
    for (mes, conta), v in sorted(por_mc.items(), key=lambda x: (x[0][1], x[0][0])):
        lines.append(f"| {mes} | {conta} | {v['n']:,} | {v['cred']:,.2f} | {v['deb']:,.2f} |")

    lines += ["",
              "## 4. Top 15 Valores Recorrentes (Candidatos a Contrato)",
              "",
              "Debitos com o mesmo valor exato - possiveis pagamentos fixos:",
              "",
              "| Valor (R$) | Ocorrencias | Sugestao |",
              "|---|---|---|"]
    for valor, qtd in top_valores[:15]:
        sug = "Cadastrar como contrato" if qtd >= 10 else ("Investigar" if qtd >= 5 else "Pode ser coincidencia")
        lines.append(f"| {valor:,.2f} | {qtd} | {sug} |")

    lines += ["",
              "## 5. Top 15 Contrapartes por CNPJ (Candidatos a Cadastro)",
              "",
              "| CNPJ | Ocorrencias |",
              "|---|---|"]
    for cnpj, qtd in top_cnpjs[:15]:
        if len(cnpj) == 14:
            cnpj_fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}"
        else:
            cnpj_fmt = cnpj
        lines.append(f"| {cnpj_fmt} | {qtd} |")

    lines += ["", "## 6. Top 10 Maiores Debitos", "",
              "| Data | Valor (R$) | Memo | Nome |",
              "|---|---|---|---|"]
    for valor, t, mes, _ in top_deb[:10]:
        memo_s = (t.memo or "")[:40].replace("|", "/")
        nome_s = (t.nome or "")[:40].replace("|", "/")
        lines.append(f"| {t.data} | {valor:,.2f} | {memo_s} | {nome_s} |")

    lines += ["", "## 7. Top 10 Maiores Creditos", "",
              "| Data | Valor (R$) | Memo | Nome |",
              "|---|---|---|---|"]
    for valor, t, mes, _ in top_cred[:10]:
        memo_s = (t.memo or "")[:40].replace("|", "/")
        nome_s = (t.nome or "")[:40].replace("|", "/")
        lines.append(f"| {t.data} | {valor:,.2f} | {memo_s} | {nome_s} |")

    # ── Novas seções: contrapartes enriquecidas via BrasilAPI/RFB ──────
    lines += [
        "",
        "## 8. Contrapartes Enriquecidas (via BrasilAPI / RFB)",
        "",
        f"Total de **{len(cache_cnpj)} CNPJs identificados** e enriquecidos com razao social.",
        "Cascata: cache local -> BrasilAPI (preferida, dados frescos) -> RFB local (fallback).",
        "",
        "### Top 20 Fornecedores por Volume Pago",
        "",
        "| Razao Social | UF | Situacao | Pagamentos | Volume (R$) |",
        "|---|---|---|---|---|",
    ]
    top_volume = sorted(volume_por_cnpj.items(), key=lambda x: -x[1])[:20]
    for cnpj, volume in top_volume:
        info = cache_cnpj.get(cnpj, {})
        razao = (info.get("razao_social") or "(nao identificado)")[:50]
        uf = info.get("uf", "-") or "-"
        sit = info.get("situacao", "?") or "?"
        qtd = cnpj_rec[cnpj]
        sit_md = f"**{sit}**" if "BAIXADA" in sit or "INAPTA" in sit else sit
        lines.append(f"| {razao} | {uf} | {sit_md} | {qtd} | {volume:,.2f} |")

    alertas = [
        (cnpj, info) for cnpj, info in cache_cnpj.items()
        if "BAIXADA" in (info.get("situacao") or "") or "INAPTA" in (info.get("situacao") or "")
    ]
    lines += [
        "",
        "## 9. ALERTAS - Contrapartes BAIXADAS / INAPTAS",
        "",
        f"**{len(alertas)} CNPJs** com situacao cadastral irregular receberam pagamentos.",
        "Para auditoria: investigar transacoes posteriores a data de baixa.",
        "",
    ]
    if alertas:
        lines += [
            "| Razao Social | UF | Situacao | Data Baixa | Aparicoes | Volume (R$) |",
            "|---|---|---|---|---|---|",
        ]
        alertas_ord = sorted(alertas, key=lambda x: -volume_por_cnpj[x[0]])
        for cnpj, info in alertas_ord:
            razao = (info.get("razao_social") or "")[:45]
            uf = info.get("uf", "-")
            sit = info.get("situacao", "?")
            data_baixa = info.get("data_situacao", "-")
            qtd = cnpj_rec[cnpj]
            volume = volume_por_cnpj[cnpj]
            lines.append(
                f"| {razao} | {uf} | **{sit}** | {data_baixa} | {qtd} | {volume:,.2f} |"
            )

    ufs = Counter()
    for cnpj, info in cache_cnpj.items():
        if info.get("uf"):
            ufs[info["uf"]] += cnpj_rec.get(cnpj, 1)
    lines += [
        "",
        "## 10. Distribuicao Geografica de Contrapartes",
        "",
        "| UF | Contrapartes (aparicoes) |",
        "|---|---|",
    ]
    for uf, n in ufs.most_common(10):
        lines.append(f"| {uf} | {n:,} |")

    total_recorrentes = sum(q for _, q in top_valores[:10])
    lines += [
        "",
        "## 11. Recomendacoes",
        "",
        f"1. **Cadastrar contratos** dos top 10 valores recorrentes -> elimina ~{total_recorrentes} transacoes",
        f"2. **Cadastrar clientes/fornecedores** com CNPJs recorrentes ({len(top_cnpjs)} candidatos)",
        f"3. **Investigar urgente** os {len(alertas)} CNPJs BAIXADOS - pagamento a empresa nao ativa",
        f"4. **Cadastrar aliases** dos {len(top_nomes)} nomes bancarios frequentes (>=5 ocorrencias)",
        f"5. **Conseguir XMLs de NF-e** elimina {totais.get(2,0):,} transacoes ({100*totais.get(2,0)/n_tot:.1f}%)",
        "",
        "## 12. Sobre os PDFs",
        "",
        "Os 6 PDFs sao **scans** dos extratos - sem texto extraivel. Como ja temos OFXs nativos",
        "dos mesmos meses (exceto fevereiro), processar os PDFs e redundante. **FEV/2026** so",
        "existe em PDF - para incluir, pedir o OFX correspondente OU rodar OCR.",
        "",
        "## 13. Integracao CNPJ - RFB / BrasilAPI",
        "",
        "O OrgConc agora enriquece contrapartes em **cascata** (api/matchers/cnpj_enricher.py):",
        "",
        "1. **Cache local JSON** (instantaneo, sem rede)",
        "2. **BrasilAPI** (preferido) - dados frescos, ~2 req/s sustentado, gratis e sem auth",
        "3. **Base RFB local** (fallback offline) - schema `cnpj.*` no Postgres",
        "",
        "Para ativar a base RFB local (sem rate limit, auditorias em massa):",
        "- Baixar dump mensal em https://www.gov.br/receitafederal/.../dados-publicos-cnpj",
        "- Descompactar em pasta unica (~30-40 GB)",
        "- Rodar `python scripts/etl_cnpj_supabase.py --dir D:\\cnpj_csv`",
        "- O enricher detecta o schema automaticamente e usa como fallback.",
    ]

    out_path = r"C:\Users\Veloso\Downloads\RELATORIO_CONSOLIDADO.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Relatorio salvo em: {out_path}")
    print(f"Total: {n_tot:,} transacoes processadas")
    print(f"Creditos: R$ {cred_total:,.2f} / Debitos: R$ {deb_total:,.2f}")
    print(f"Saldo de fluxo: R$ {cred_total + deb_total:,.2f}")


if __name__ == "__main__":
    main()
