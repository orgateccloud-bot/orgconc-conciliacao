"""Testes para api/services/carta_constatacao.py — gerador automático."""
from __future__ import annotations

from datetime import date

import pytest

from api.services.carta_constatacao import (
    _fmt_brl,
    renderizar_carta_md,
    renderizar_html,
)


def _dados_mock(risco_total=5_000_000.0, n_fornecedores=50):
    """Mock minimal dos dados que vem de coletar_dados_cliente."""

    class _Cliente:
        id = "uuid-1"
        nome = "LOCAR TRANSPORTE DE BOVINOS LTDA"
        cnpj = "05.509.396/0001-10"

    class _ConfRow:
        def __init__(self, cnpj, razao, vol_pago, vol_nf, conf, risco):
            self.cnpj_fornecedor = cnpj
            self.razao_social = razao
            self.volume_pago = vol_pago
            self.volume_nf = vol_nf
            self.conformidade_pct = conf
            self.n_pagamentos = 5
            self.n_nfes = 1 if vol_nf > 0 else 0
            self.risco_classe = "CRITICO"
            self.risco_tributario_anual = risco

    criticos = [
        _ConfRow(f"cnpj{i}", f"Fornecedor {i}", 100_000, 0, 0.0, 30_000)
        for i in range(5)
    ]
    return {
        "cliente": _Cliente(),
        "total_fornecedores": n_fornecedores,
        "risco_total": risco_total,
        "by_classe": {"BAIXO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": risco_total},
        "count_classe": {"BAIXO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 5},
        "criticos": criticos,
    }


def test_fmt_brl():
    assert _fmt_brl(1500.5) == "R$ 1.500,50"
    assert _fmt_brl(0) == "R$ 0,00"
    assert _fmt_brl(1_234_567.89) == "R$ 1.234.567,89"


def test_renderizar_carta_md_contem_cliente_e_risco():
    md = renderizar_carta_md(_dados_mock(risco_total=3_363_620), versao="auto-7")
    assert "LOCAR TRANSPORTE DE BOVINOS" in md
    assert "auto-7" in md
    assert "R$ 3.363.620,00" in md
    assert "CRITICO" in md
    assert "RIR/2018" in md  # fundamentação normativa


def test_renderizar_carta_md_tem_secoes_essenciais():
    md = renderizar_carta_md(_dados_mock(), versao="auto-1")
    for secao in (
        "# CARTA DE CONSTATACAO",
        "## 1. Preambulo",
        "## 2. Sumario por Classe de Risco",
        "## 4. Fundamentacao Normativa",
        "## 5. Recomendacoes",
        "## 6. Conclusao",
    ):
        assert secao in md, f"Faltou secao: {secao}"


def test_renderizar_carta_md_sem_criticos():
    """Quando não há fornecedores críticos, omite secao 3."""
    dados = _dados_mock()
    dados["criticos"] = []
    md = renderizar_carta_md(dados, versao="auto-2")
    assert "Top 10 Fornecedores CRITICOS" not in md


def test_renderizar_html_contem_body_e_estilo():
    md = renderizar_carta_md(_dados_mock(), versao="auto-1")
    html = renderizar_html(md, titulo="Carta Teste")
    assert "<!DOCTYPE html>" in html
    assert "<style>" in html
    assert "Carta Teste" in html
    # Markdown convertido em HTML
    assert "<h1" in html or "<h2" in html


def test_renderizar_carta_md_versao_no_ref():
    md = renderizar_carta_md(_dados_mock(), versao="custom-xyz")
    assert "custom-xyz" in md
