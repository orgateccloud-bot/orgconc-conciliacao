"""Testes para api/matchers/conformidade.py — score + flags."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from api.matchers.conformidade import (
    ConformidadeScore,
    _classe,
    _detectar_flags,
    _extrair_cnpj,
    calcular_conformidade_fornecedor,
    classificar_risco,
)
from api.matchers.xml_fiscal import DocumentoFiscalLido


@dataclass
class _Tx:
    data: date
    valor: float
    nome: str = ""
    memo: str = ""
    fitid: str = ""
    tipo: str = "DEBIT"


def _doc(emit_cnpj="12345678000190", valor=1000.0, tipo="NF-e"):
    return DocumentoFiscalLido(
        tipo=tipo, modelo="55", chave="x" * 44, numero="1", serie="1",
        data_emissao="2026-04-15", emit_cnpj=emit_cnpj, emit_nome="Forn",
        emit_uf="GO", dest_cnpj="", dest_nome="", valor_total=valor,
    )


# ────────────────────────────────────────────────────────────────────────
# _classe e _detectar_flags
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("pct,esperado", [
    (100, "BAIXO"),
    (85, "BAIXO"),
    (80, "BAIXO"),
    (79, "MEDIO"),
    (50, "MEDIO"),
    (49, "ALTO"),
    (20, "ALTO"),
    (19, "CRITICO"),
    (0, "CRITICO"),
])
def test_classe_buckets(pct, esperado):
    assert _classe(pct) == esperado


def test_flag_rede_frota_type():
    flags = _detectar_flags(
        nome="REDE FROTA SOLUTIONS", cnae="6619", volume_pago=200_000,
        volume_nf=0, is_mei=False, n_ctes=0,
    )
    assert "REDE_FROTA_TYPE" in flags


def test_flag_mei_sem_cte():
    flags = _detectar_flags(
        nome="JOAO CAMINHONEIRO", cnae="4930-2", volume_pago=50_000,
        volume_nf=50_000, is_mei=True, n_ctes=0,
    )
    assert "MEI_SEM_CTE" in flags


def test_flag_mei_com_cte_nao_dispara():
    flags = _detectar_flags(
        nome="JOAO CAMINHONEIRO", cnae="4930-2", volume_pago=50_000,
        volume_nf=50_000, is_mei=True, n_ctes=3,
    )
    assert "MEI_SEM_CTE" not in flags


def test_flag_parte_relacionada_nome_empresa_do_socio():
    """Fornecedor cujo nome carrega o nome de um sócio do cliente."""
    flags = _detectar_flags(
        nome="JOAO SILVA LOCADORA E TRANSPORTES", cnae="", volume_pago=100,
        volume_nf=100, is_mei=False, n_ctes=0,
        nomes_socios=["Joao Silva"],
    )
    assert "PARTE_RELACIONADA" in flags


def test_flag_parte_relacionada_por_socio():
    flags = _detectar_flags(
        nome="MARIA SOUZA TRANSPORTES", cnae="", volume_pago=100,
        volume_nf=100, is_mei=False, n_ctes=0,
        nomes_socios=["Maria Souza"],
    )
    assert "PARTE_RELACIONADA" in flags


def test_sem_socio_correspondente_nao_dispara_parte_relacionada():
    """Sem sócio conhecido casando o nome, não há parte relacionada (data-driven)."""
    flags = _detectar_flags(
        nome="TRANSPORTADORA EXEMPLO LTDA", cnae="", volume_pago=100,
        volume_nf=100, is_mei=False, n_ctes=0,
        nomes_socios=["Joao Silva"],
    )
    assert "PARTE_RELACIONADA" not in flags


# ────────────────────────────────────────────────────────────────────────
# calcular_conformidade_fornecedor
# ────────────────────────────────────────────────────────────────────────


def test_score_100_quando_pagamento_e_nf_iguais():
    docs = [_doc(emit_cnpj="12345678000190", valor=1500.0)]
    txs = [_Tx(data=date(2026, 4, 16), valor=-1500.0, nome="FORN 12.345.678/0001-90")]
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert len(scores) == 1
    assert scores[0].conformidade_pct >= 99.9
    assert scores[0].risco_classe == "BAIXO"


def test_score_zero_quando_paga_sem_nf():
    docs = []
    txs = [_Tx(data=date(2026, 4, 16), valor=-200_000.0, nome="REDE FROTA 24.478.438/0001-48")]
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert len(scores) == 1
    assert scores[0].conformidade_pct == 0.0
    assert scores[0].risco_classe == "CRITICO"
    assert "REDE_FROTA_TYPE" in scores[0].flags


def test_score_parcial_metade():
    docs = [_doc(emit_cnpj="12345678000190", valor=500.0)]
    txs = [_Tx(data=date(2026, 4, 16), valor=-1000.0, nome="X 12.345.678/0001-90")]
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert 49.0 < scores[0].conformidade_pct < 51.0
    assert scores[0].risco_classe in ("MEDIO", "ALTO")


def test_classificar_risco_eleva_para_critico_com_flag():
    """A presença de REDE_FROTA_TYPE ou MEI_SEM_CTE deve forçar CRITICO."""
    score = ConformidadeScore(
        cnpj_fornecedor="111", razao_social="x", periodo_inicio=None, periodo_fim=None,
        volume_pago=100, volume_nf=100, conformidade_pct=100, n_pagamentos=1,
        n_nfes=1, risco_classe="BAIXO", flags=["REDE_FROTA_TYPE"],
    )
    assert classificar_risco(score) == "CRITICO"


def test_score_sem_pagamento_mas_com_nf():
    """Documento emitido sem pagamento OFX correspondente — conformidade 100% (tem documento)."""
    docs = [_doc(emit_cnpj="12345678000190", valor=1000.0)]
    txs = []
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert scores[0].conformidade_pct == 100.0
    assert scores[0].risco_classe == "BAIXO"


# ────────────────────────────────────────────────────────────────────────
# _extrair_cnpj — formatado, bruto (14 dígitos) e ausência
# ────────────────────────────────────────────────────────────────────────


def test_extrair_cnpj_formatado_com_barra():
    """CNPJ no formato 00.000.000/0000-00 (separador barra)."""
    tx = _Tx(data=date(2026, 4, 1), valor=-10.0, nome="FORN 12.345.678/0001-90")
    assert _extrair_cnpj(tx) == "12345678000190"


def test_extrair_cnpj_formatado_com_espaco():
    """A regex aceita espaço no lugar da barra antes do bloco de filial."""
    tx = _Tx(data=date(2026, 4, 1), valor=-10.0, memo="PIX 12.345.678 0001-90")
    assert _extrair_cnpj(tx) == "12345678000190"


def test_extrair_cnpj_bruto_14_digitos():
    """Sem pontuação: 14 dígitos contíguos no memo (RX_CNPJ_BRUTO)."""
    tx = _Tx(data=date(2026, 4, 1), valor=-10.0, memo="TED 12345678000190 PAGTO")
    assert _extrair_cnpj(tx) == "12345678000190"


def test_extrair_cnpj_ausente_retorna_none():
    """Sem CNPJ identificável → None."""
    tx = _Tx(data=date(2026, 4, 1), valor=-10.0, nome="MERCADO", memo="COMPRA CARTAO")
    assert _extrair_cnpj(tx) is None


def test_extrair_cnpj_nome_e_memo_none_nao_quebra():
    """nome/memo None devem ser tratados como string vazia (sem AttributeError)."""
    @dataclass
    class _TxNone:
        data: date
        valor: float
        nome = None
        memo = None
    tx = _TxNone(data=date(2026, 4, 1), valor=-10.0)
    assert _extrair_cnpj(tx) is None


# ────────────────────────────────────────────────────────────────────────
# calcular_conformidade_fornecedor — ramos de agregação
# ────────────────────────────────────────────────────────────────────────


def test_credito_e_pagamento_sem_cnpj_sao_ignorados():
    """Transações positivas (crédito) e sem CNPJ não geram fornecedor."""
    txs = [
        _Tx(data=date(2026, 4, 1), valor=500.0, nome="DEPOSITO 12.345.678/0001-90"),
        _Tx(data=date(2026, 4, 2), valor=-300.0, nome="SEM CNPJ AQUI"),
    ]
    scores = calcular_conformidade_fornecedor([], txs)
    assert scores == []


def test_data_string_valida_define_periodo():
    """Quando t.data é string AAAA-MM-DD, vira date e alimenta período."""
    txs = [
        _Tx(data="2026-04-10", valor=-100.0, nome="X 12.345.678/0001-90"),
        _Tx(data="2026-04-20", valor=-100.0, nome="X 12.345.678/0001-90"),
    ]
    scores = calcular_conformidade_fornecedor([], txs)
    assert len(scores) == 1
    assert scores[0].periodo_inicio == date(2026, 4, 10)
    assert scores[0].periodo_fim == date(2026, 4, 20)


def test_data_string_invalida_sem_periodo():
    """String de data inválida cai no except ValueError → sem período."""
    txs = [_Tx(data="data-invalida", valor=-100.0, nome="X 12.345.678/0001-90")]
    scores = calcular_conformidade_fornecedor([], txs)
    assert len(scores) == 1
    assert scores[0].periodo_inicio is None
    assert scores[0].periodo_fim is None


def test_documento_sem_emit_cnpj_e_ignorado():
    """NF-e sem emit_cnpj não entra na agregação de documentos."""
    docs = [_doc(emit_cnpj="", valor=1000.0)]
    scores = calcular_conformidade_fornecedor(docs, [])
    assert scores == []


def test_documento_cancelado_nao_conta_como_cobertura():
    """NF CANCELADA não soma volume_nf — mas se há pagamento, o gap aparece."""
    cancelada = _doc(emit_cnpj="12345678000190", valor=1000.0)
    cancelada.situacao = "CANCELADA"
    txs = [_Tx(data=date(2026, 4, 1), valor=-1000.0, nome="X 12.345.678/0001-90")]
    scores = calcular_conformidade_fornecedor([cancelada], txs)
    assert len(scores) == 1
    assert scores[0].volume_nf == 0.0
    assert scores[0].conformidade_pct == 0.0
    assert scores[0].n_nfes == 0


def test_documento_denegado_nao_conta_como_cobertura():
    denegada = _doc(emit_cnpj="12345678000190", valor=1000.0)
    denegada.situacao = "DENEGADA"
    scores = calcular_conformidade_fornecedor([denegada], [])
    # Documento inválido e sem pagamento → CNPJ não entra no universo
    assert scores == []


def test_cte_incrementa_n_ctes_evita_mei_sem_cte():
    """CT-e do MEI de transporte deve zerar a flag MEI_SEM_CTE (n_ctes>0)."""
    cte = _doc(emit_cnpj="99999999000199", valor=5000.0, tipo="CT-e")
    txs = [_Tx(data=date(2026, 4, 1), valor=-5000.0, nome="MEI 99.999.999/0001-99")]
    scores = calcular_conformidade_fornecedor(
        [cte], txs,
        cnae_por_cnpj={"99999999000199": "4930-2"},
        is_mei_por_cnpj={"99999999000199": True},
    )
    assert len(scores) == 1
    assert "MEI_SEM_CTE" not in scores[0].flags


def test_mei_de_transporte_sem_cte_dispara_flag_via_calculo():
    """Pagamento a MEI de transporte (CNAE 4930) sem nenhum CT-e → MEI_SEM_CTE."""
    nfe = _doc(emit_cnpj="99999999000199", valor=5000.0, tipo="NF-e")
    txs = [_Tx(data=date(2026, 4, 1), valor=-5000.0, nome="MEI 99.999.999/0001-99")]
    scores = calcular_conformidade_fornecedor(
        [nfe], txs,
        cnae_por_cnpj={"99999999000199": "4930-2"},
        is_mei_por_cnpj={"99999999000199": True},
    )
    assert "MEI_SEM_CTE" in scores[0].flags
    assert classificar_risco(scores[0]) == "CRITICO"


def test_documento_valor_zero_gera_pct_zero():
    """Doc com emit_cnpj válido mas valor_total 0 e sem pagamento → pct 0.0 (ramo else)."""
    doc = _doc(emit_cnpj="12345678000190", valor=0.0)
    scores = calcular_conformidade_fornecedor([doc], [])
    assert len(scores) == 1
    assert scores[0].conformidade_pct == 0.0
    # vol_pago == 0 → risco_classe forçado a BAIXO independentemente do pct
    assert scores[0].risco_classe == "BAIXO"


def test_pct_capado_em_100_quando_nf_excede_pagamento():
    """volume_nf > volume_pago não passa de 100% (cap min(100, ...))."""
    docs = [_doc(emit_cnpj="12345678000190", valor=3000.0)]
    txs = [_Tx(data=date(2026, 4, 1), valor=-1000.0, nome="X 12.345.678/0001-90")]
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert scores[0].conformidade_pct == 100.0


def test_razao_social_truncada_em_200():
    """razao_social é cortada em 200 caracteres."""
    nome_longo = "A" * 300
    doc = _doc(emit_cnpj="12345678000190", valor=1000.0)
    doc.emit_nome = nome_longo
    scores = calcular_conformidade_fornecedor([doc], [])
    assert len(scores[0].razao_social) == 200


def test_ordenacao_por_volume_pago_desc():
    """Resultados saem ordenados por volume_pago decrescente."""
    docs = []
    txs = [
        _Tx(data=date(2026, 4, 1), valor=-100.0, nome="P 11.111.111/0001-11"),
        _Tx(data=date(2026, 4, 1), valor=-900.0, nome="G 22.222.222/0001-22"),
    ]
    scores = calcular_conformidade_fornecedor(docs, txs)
    assert [s.volume_pago for s in scores] == [900.0, 100.0]


def test_razao_social_prefere_nome_do_documento():
    """Quando há doc e pagamento, a razão social vem do documento (emit_nome)."""
    doc = _doc(emit_cnpj="12345678000190", valor=1000.0)
    doc.emit_nome = "RAZAO DO DOCUMENTO"
    txs = [_Tx(data=date(2026, 4, 1), valor=-1000.0, nome="NOME DO EXTRATO 12.345.678/0001-90")]
    scores = calcular_conformidade_fornecedor([doc], txs)
    assert scores[0].razao_social == "RAZAO DO DOCUMENTO"


# ────────────────────────────────────────────────────────────────────────
# _detectar_flags — bordas
# ────────────────────────────────────────────────────────────────────────


def test_rede_frota_limite_inferior_dispara():
    """volume_pago exatamente 100k com NF zero dispara REDE_FROTA_TYPE."""
    flags = _detectar_flags(
        nome="FROTA", cnae="", volume_pago=100_000, volume_nf=0,
        is_mei=False, n_ctes=0,
    )
    assert "REDE_FROTA_TYPE" in flags


def test_rede_frota_abaixo_limite_nao_dispara():
    flags = _detectar_flags(
        nome="FROTA", cnae="", volume_pago=99_999.99, volume_nf=0,
        is_mei=False, n_ctes=0,
    )
    assert "REDE_FROTA_TYPE" not in flags


def test_rede_frota_com_nf_nao_dispara():
    """Mesmo com volume alto, se houver NF (>0) a flag não aparece."""
    flags = _detectar_flags(
        nome="FROTA", cnae="", volume_pago=200_000, volume_nf=1.0,
        is_mei=False, n_ctes=0,
    )
    assert "REDE_FROTA_TYPE" not in flags


def test_mei_sem_cte_so_para_cnae_de_transporte():
    """MEI sem CT-e mas CNAE não-transporte não dispara MEI_SEM_CTE."""
    flags = _detectar_flags(
        nome="MEI COMERCIO", cnae="4711", volume_pago=10_000, volume_nf=10_000,
        is_mei=True, n_ctes=0,
    )
    assert "MEI_SEM_CTE" not in flags


def test_mei_sem_cte_so_quando_is_mei():
    """CNAE de transporte sem CT-e mas não-MEI não dispara a flag."""
    flags = _detectar_flags(
        nome="TRANSPORTADORA", cnae="4930-2", volume_pago=10_000, volume_nf=10_000,
        is_mei=False, n_ctes=0,
    )
    assert "MEI_SEM_CTE" not in flags


def test_parte_relacionada_socio_curto_nao_dispara():
    """Sócio com nome < 4 caracteres é ignorado (guarda de comprimento)."""
    flags = _detectar_flags(
        nome="BANANA TRANSPORTES", cnae="", volume_pago=100, volume_nf=100,
        is_mei=False, n_ctes=0, nomes_socios=["Ana"],
    )
    assert "PARTE_RELACIONADA" not in flags


def test_parte_relacionada_substring_sem_fronteira_nao_dispara():
    """Match exige fronteira de palavra (\\b): substring colada não conta."""
    flags = _detectar_flags(
        nome="JOAOZINHO TRANSPORTES", cnae="", volume_pago=100, volume_nf=100,
        is_mei=False, n_ctes=0, nomes_socios=["Joao"],
    )
    assert "PARTE_RELACIONADA" not in flags


def test_parte_relacionada_socio_vazio_ou_none_ignorado():
    """Sócios vazios/None na lista não quebram nem disparam a flag."""
    flags = _detectar_flags(
        nome="JOAO SILVA TRANSPORTES", cnae="", volume_pago=100, volume_nf=100,
        is_mei=False, n_ctes=0, nomes_socios=["", None, "JOAO SILVA"],
    )
    assert "PARTE_RELACIONADA" in flags


def test_detectar_flags_nome_none_nao_quebra():
    """nome None vira string vazia (sem AttributeError no .upper())."""
    flags = _detectar_flags(
        nome=None, cnae="", volume_pago=50, volume_nf=50,
        is_mei=False, n_ctes=0,
    )
    assert flags == []


# ────────────────────────────────────────────────────────────────────────
# classificar_risco — ramo sem flag crítica
# ────────────────────────────────────────────────────────────────────────


def test_classificar_risco_mei_sem_cte_eleva_critico():
    score = ConformidadeScore(
        cnpj_fornecedor="111", razao_social="x", periodo_inicio=None, periodo_fim=None,
        volume_pago=100, volume_nf=100, conformidade_pct=100, n_pagamentos=1,
        n_nfes=1, risco_classe="BAIXO", flags=["MEI_SEM_CTE"],
    )
    assert classificar_risco(score) == "CRITICO"


def test_classificar_risco_sem_flag_mantem_classe():
    """Sem flag crítica, retorna o risco_classe original (ramo final)."""
    score = ConformidadeScore(
        cnpj_fornecedor="111", razao_social="x", periodo_inicio=None, periodo_fim=None,
        volume_pago=100, volume_nf=30, conformidade_pct=30, n_pagamentos=1,
        n_nfes=1, risco_classe="ALTO", flags=["PARTE_RELACIONADA"],
    )
    assert classificar_risco(score) == "ALTO"
