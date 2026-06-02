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


def test_anualizado_global_nao_corrompido_por_loop_mei():
    """Regressão: o loop de classificação de MEIs não pode sobrescrever a variável
    `anualizado` (giro anualizado da EMPRESA). Antes, stats['anualizado'] saía com o
    valor do último MEI (centenas de R$) em vez do giro real (milhões), enquanto
    stats['multiplo'] permanecia correto — inconsistência no Sumário do MD/PDF."""
    from api.matchers.regime_fiscal import TETO_SIMPLES_EPP

    # Empresa com giro em milhões + 1 MEI (porte via cache) que aciona o loop.
    txs = [
        _tx("2026-01-10", -3_000_000.0, nome="FORN GRANDE 11.222.333/0001-81"),
        _tx("2026-02-10", 3_000_000.0, nome="CLIENTE 11.222.333/0001-81"),
        _tx("2026-03-10", -300.0, nome="MEI 44.555.666/0001-22"),
    ]
    todos, saldos = laudo.montar_dados(txs)
    cache = {"44555666000122": {
        "porte": "MICRO EMPRESA", "razao_social": "MEI PEQUENO ME",
        "cnae_principal": "4930202", "situacao": "ATIVA",
    }}
    laudo.EMPRESA = laudo.construir_empresa("11222333000181", cache)
    _, stats = laudo.gerar_laudo_workbook(todos, saldos, cache)

    # Anualizado é o da empresa (milhões), não o do MEI (centenas) — pega o bug.
    assert stats["anualizado"] > TETO_SIMPLES_EPP
    # E casa com o múltiplo (tolerância p/ arredondamento do múltiplo em 2 casas).
    assert abs(stats["anualizado"] - stats["multiplo"] * TETO_SIMPLES_EPP) < TETO_SIMPLES_EPP * 0.02


def test_construir_empresa_sem_cache_nao_vaza_dados():
    emp = laudo.construir_empresa("11222333000181", {})
    assert emp["cnpj_basico"] == "11222333000181"
    # Sem cache, todos os campos textuais ficam genéricos ("—") — nenhum dado de cliente.
    assert emp["razao_social"] == "—"
    assert emp["socio_nome"] == "—"
