"""Smoke test do núcleo do laudo forense (api/services/laudo_forense).

Garante que o núcleo reusável (compartilhado por CLI e API) monta as 11 abas a
partir de transações sintéticas — sem rede nem cache populado — e que a empresa
montada sem cache NÃO vaza dados de cliente.
"""
from __future__ import annotations

import api.services.laudo_forense as laudo
from api.matchers.cascata import Transacao

ABAS = [
    "1. Capa", "2. Identificacao", "3. Resumo Executivo", "4. Transacoes",
    "5. Disposicoes", "6. Risk Heatmap", "7. CNPJs", "8. Partes Relacionadas",
    "9. MEIs Teto", "10. Status Tributario", "11. Pos-Baixa",
]


def _tx(data: str, valor: float, nome: str = "FORNECEDOR TESTE",
        memo: str = "PAGAMENTO PIX 11 222 333 0001 81") -> Transacao:
    return Transacao(
        data=data, tipo="DEBIT" if valor < 0 else "CREDIT", valor=valor,
        fitid=f"{data}-{valor}", memo=memo, nome=nome, conta="AG 1 / CC 99999-9",
    )


def test_montar_dados_buckets_por_mes():
    txs = [_tx("2026-01-05", -1000.0), _tx("2026-01-20", 3000.0), _tx("2026-02-10", -500.0)]
    todos, saldos = laudo.montar_dados(txs)
    assert len(todos) == 3
    assert list(saldos.keys()) == ["JAN/2026", "FEV/2026"]   # ordem cronológica derivada
    assert saldos["JAN/2026"]["n"] == 2


def test_gerar_laudo_workbook_11_abas():
    txs = [
        _tx("2026-01-05", -1500.0), _tx("2026-01-20", 8000.0),
        _tx("2026-02-10", -500.0, nome="OUTRO FORN"), _tx("2026-03-15", -12000.0),
    ]
    todos, saldos = laudo.montar_dados(txs)
    laudo.EMPRESA = laudo.construir_empresa("11222333000181", {})
    wb, stats = laudo.gerar_laudo_workbook(todos, saldos, {})
    assert wb.sheetnames == ABAS
    assert stats["n_total"] == 4
    assert stats["n_meses"] == 3
    # gerar_md não pode quebrar sem MEIs/pós-baixa (regressão: total_exc indefinido)
    md, totais = laudo.gerar_md(stats)
    assert "Sumario Executivo" in md
    assert isinstance(totais, dict) and "total_exc" in totais


def test_construir_empresa_sem_cache_nao_vaza_dados():
    emp = laudo.construir_empresa("11222333000181", {})
    assert emp["cnpj_basico"] == "11222333000181"
    # Sem cache, todos os campos textuais ficam genéricos ("—") — nenhum dado de cliente.
    assert emp["razao_social"] == "—"
    assert emp["socio_nome"] == "—"


def test_preparar_calculo_laudo_fase_pura():
    """A fase de cálculo extraída (refactor 2.4) devolve os pré-cálculos sem render."""
    memo_cnpj = "PAGAMENTO PIX 11.222.333/0001-81"  # pontuado: RX_CNPJ não pega espaços
    txs = [
        _tx("2026-01-05", -1500.0, memo=memo_cnpj), _tx("2026-01-20", 8000.0, memo=memo_cnpj),
        _tx("2026-02-10", -500.0, nome="OUTRO FORN", memo=memo_cnpj),
    ]
    todos, saldos = laudo.montar_dados(txs)
    cache = {"11222333000181": {
        "razao_social": "ACME LTDA", "situacao": "BAIXADA",
        "data_situacao": "2025-12-01", "porte": "ME",
    }}
    calc = laudo.preparar_calculo_laudo(todos, saldos, cache)

    assert calc["n_total"] == 3
    assert calc["meses"] == ["JAN/2026", "FEV/2026"]
    assert calc["n_meses"] == 2
    assert calc["periodo_str"] == "05/01/2026 a 10/02/2026"
    assert round(calc["cred_total"], 2) == 8000.0
    assert round(calc["deb_total"], 2) == -2000.0
    assert round(calc["volume_bruto"], 2) == 10000.0
    assert calc["anualizado"] > 0 and calc["multiplo"] >= 0
    # Disposições classificadas: memo com CNPJ baixado ANTES da transação → pós-baixa.
    disps = calc["todas_disps"]
    assert len(disps) == 3
    assert any(d.disposicao == "ALERTA_POS_BAIXA" for d in disps)
    assert all(d.contraparte == "ACME LTDA" for d in disps if d.cnpj)
    assert "agg" in calc and calc["agg"] is not None


def test_preparar_calculo_alimenta_workbook_identico():
    """gerar_laudo_workbook consome a fase pura — stats espelham o cálculo."""
    txs = [_tx("2026-01-05", -100.0), _tx("2026-02-01", 300.0)]
    todos, saldos = laudo.montar_dados(txs)
    laudo.EMPRESA = laudo.construir_empresa("11222333000181", {})
    calc = laudo.preparar_calculo_laudo(todos, saldos, {})
    _, stats = laudo.gerar_laudo_workbook(todos, saldos, {})
    for chave in ("n_total", "n_meses", "periodo_str", "cred_total",
                  "deb_total", "volume_bruto", "anualizado", "multiplo"):
        assert stats[chave] == calc[chave], chave


def test_stats_anualizado_nao_e_sombreado_pelo_loop_de_meis():
    """Regressão do bug 59401c1e (reintroduzido na reconciliação #59 e refixado):
    o loop da aba 9 (MEIs) usava a variável `anualizado` e SOMBREAVA o anualizado
    da EMPRESA — stats/MD passavam a mostrar o anualizado do último MEI.
    """
    memo_cnpj = "PAGAMENTO PIX 11.222.333/0001-81"
    txs = [
        _tx("2026-01-05", -50_000.0, memo=memo_cnpj),
        _tx("2026-02-10", -80_000.0, memo=memo_cnpj),
        _tx("2026-03-15", 900_000.0, memo="RECEBIMENTO CLIENTE"),
    ]
    todos, saldos = laudo.montar_dados(txs)
    # MEI no cache → o loop da aba 9 processa e (no bug) poluía `anualizado`.
    cache = {"11222333000181": {
        "razao_social": "MEI TESTE", "porte": "MICRO EMPRESA",
        "cnae_principal": "4930201", "situacao": "ATIVA",
    }}
    laudo.EMPRESA = laudo.construir_empresa("99888777000166", {})
    _, stats = laudo.gerar_laudo_workbook(todos, saldos, cache)

    # O anualizado do stats DEVE ser o da empresa (fase de cálculo/motor)…
    calc = laudo.preparar_calculo_laudo(todos, saldos, cache)
    assert stats["anualizado"] == calc["anualizado"]
    # …e NÃO o do MEI (deb*12/meses_obs).
    anualizado_mei = (50_000.0 + 80_000.0) * 12 / max(stats["meses_obs"], 1)
    assert stats["anualizado"] != anualizado_mei
    assert stats["meis"], "cenário deve ter MEI processado na aba 9"
    # O MD imprime o valor da empresa no Sumário.
    md, _ = laudo.gerar_md(stats)
    assert f"R$ {calc['anualizado']:,.2f}" in md
