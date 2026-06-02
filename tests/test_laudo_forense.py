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


def test_construir_empresa_sem_cache_nao_vaza_dados():
    emp = laudo.construir_empresa("11222333000181", {})
    assert emp["cnpj_basico"] == "11222333000181"
    # Sem cache, todos os campos textuais ficam genéricos ("—") — nenhum dado de cliente.
    assert emp["razao_social"] == "—"
    assert emp["socio_nome"] == "—"
