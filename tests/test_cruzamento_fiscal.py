"""Testes para api/matchers/cruzamento_fiscal.py — cruzamento doc x OFX."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


from api.matchers.cruzamento_fiscal import cruzar, resumo
from api.matchers.xml_fiscal import DocumentoFiscalLido


@dataclass
class _Transacao:
    """Minimal stub de Transacao do OFX (suficiente para cruzamento)."""
    data: date
    valor: float
    nome: str = ""
    memo: str = ""
    fitid: str = ""
    tipo: str = "DEBIT"


def _doc(chave="abc"*14 + "ab", valor=1000.0, emit_cnpj="12345678000190", data="2026-04-15", tipo="NF-e"):
    return DocumentoFiscalLido(
        tipo=tipo, modelo="55", chave=chave, numero="1", serie="1",
        data_emissao=data, emit_cnpj=emit_cnpj, emit_nome="Fornecedor",
        emit_uf="GO", dest_cnpj="99888777000166", dest_nome="EMPRESA EXEMPLO",
        valor_total=valor,
    )


def _tx(valor=-1000.0, data=date(2026, 4, 16), nome="FORNECEDOR 12.345.678/0001-90"):
    return _Transacao(data=data, valor=valor, nome=nome)


def test_match_casado_por_cnpj_e_valor():
    docs = [_doc(valor=1500.0)]
    txs = [_tx(valor=-1500.0)]
    r = cruzar(docs, txs)
    statuses = [x.status for x in r]
    assert "CASADO" in statuses
    casado = [x for x in r if x.status == "CASADO"][0]
    assert casado.diferenca_valor < 0.01


def test_match_valor_divergente():
    docs = [_doc(valor=1500.0)]
    txs = [_tx(valor=-1499.50)]  # diferente do limite tolerancia
    r = cruzar(docs, txs)
    statuses = [x.status for x in r]
    assert "VALOR_DIVERGENTE" in statuses


def test_sem_pagamento_para_documento_emitido():
    docs = [_doc(emit_cnpj="99999999000199")]
    txs = []
    r = cruzar(docs, txs)
    assert len(r) == 1
    assert r[0].status == "SEM_PAGAMENTO"


def test_sem_nf_para_pagamento_sem_documento():
    docs = []
    txs = [_tx(valor=-1000.0, nome="REDE FROTA SOLUTIONS 24.478.438/0001-48")]
    r = cruzar(docs, txs)
    assert len(r) == 1
    assert r[0].status == "SEM_NF"


def test_entrada_nao_gera_gap():
    """Transações positivas (entradas) não devem gerar SEM_NF."""
    docs = []
    txs = [_Transacao(data=date(2026, 5, 1), valor=+5000.0, nome="RECEBIMENTO PIX")]
    r = cruzar(docs, txs)
    assert all(x.status != "SEM_NF" for x in r)


def test_janela_temporal_excedida():
    """Documento de fevereiro x pagamento de maio (>30 dias) deve gerar SEM_PAGAMENTO."""
    docs = [_doc(valor=1000.0, data="2026-02-01")]
    txs = [_tx(valor=-1000.0, data=date(2026, 5, 1))]
    r = cruzar(docs, txs)
    assert any(x.status == "SEM_PAGAMENTO" for x in r)
    assert any(x.status == "SEM_NF" for x in r)


def test_resumo_agrega_por_status():
    docs = [_doc(valor=1500.0), _doc(chave="d2" * 22, valor=2000.0, emit_cnpj="99999999000199")]
    txs = [_tx(valor=-1500.0)]
    r = cruzar(docs, txs)
    s = resumo(r)
    assert s["total"] == len(r)
    assert "CASADO" in s["por_status"]
    assert "SEM_PAGAMENTO" in s["por_status"]
    assert s["volume_por_status"]["CASADO"] == 1500.0


def test_match_cnpj_formatado_no_memo():
    """CNPJ formatado com pontos/barras no memo OFX deve ser extraído."""
    docs = [_doc(valor=2500.0, emit_cnpj="12345678000190")]
    txs = [_Transacao(
        data=date(2026, 4, 16),
        valor=-2500.0,
        nome="FORNECEDOR",
        memo="12.345.678/0001-90 PAGAMENTO",
    )]
    r = cruzar(docs, txs)
    assert any(x.status == "CASADO" for x in r)


def test_resumo_vazio():
    s = resumo([])
    assert s["total"] == 0
    assert s["por_status"] == {}
