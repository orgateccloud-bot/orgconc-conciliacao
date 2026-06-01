"""Golden tests do orquestrador forense — achados determinísticos ancorados na
metodologia do laudo real (regime, smurfing, carrossel, pós-baixa, retenção PJ)."""
from __future__ import annotations

from api.matchers.auditoria_forense import analisar_auditoria, resumo_para_dict
from api.matchers.cascata import Transacao


def _tx(data, valor, memo="", nome=""):
    return Transacao(
        data=data, tipo="CREDIT" if valor > 0 else "DEBIT", valor=valor,
        fitid=f"{data}-{valor}", memo=memo, nome=nome,
    )


def test_regime_caso_referencia_incompativel():
    # ~R$ 70M em ~4,5 meses → dezenas de vezes o teto EPP (caso LOCAR)
    txs = [
        _tx("2026-01-02", 35_203_688.26, memo="CREDITOS DO PERIODO"),
        _tx("2026-05-14", -35_049_842.12, memo="DEBITOS DO PERIODO"),
    ]
    r = analisar_auditoria(txs)
    assert r.regime.multiplo_do_teto > 35
    assert r.regime.classe == "CRITICO"
    assert r.regime.incompativel is True


def test_smurfing_detectado():
    cnpj = "FORNECEDOR 12.345.678/0001-90"
    txs = [_tx("2026-02-10", -9_000, nome=cnpj) for _ in range(3)]
    r = analisar_auditoria(txs)
    assert r.smurfing_qtd >= 3
    assert any("SMURFING" in d.sinais for d in r.top_disposicoes)


def test_carrossel_detectado():
    cnpj = "EMPRESA 11.222.333/0001-44"
    txs = [_tx("2026-02-10", -5_000, nome=cnpj), _tx("2026-02-11", 5_000, nome=cnpj)]
    r = analisar_auditoria(txs)
    assert r.carrossel_qtd >= 1
    assert any("CARROSSEL" in d.sinais for d in r.top_disposicoes)


def test_pos_baixa_com_cadastro_e_critico():
    txs = [_tx("2026-05-13", -10_000, nome="PG 63.567.345/0001-41")]
    cadastro = {"63567345000141": {"situacao": "BAIXADA", "data_situacao": "2026-03-11", "porte": "DEMAIS"}}
    r = analisar_auditoria(txs, cadastro=cadastro)
    assert r.pos_baixa_qtd == 1
    assert any("ALERTA_POS_BAIXA" in d.sinais for d in r.top_disposicoes)
    assert r.top_disposicoes[0].risco_classe in ("CRITICO", "ALTO")


def test_retencao_pj_6_15pct():
    # PIX a PJ (CNPJ identificado) → retenção estimada 6,15% (metodologia do laudo)
    txs = [_tx("2026-02-10", -10_000, memo="PIX ENVIADO", nome="FORN 12.345.678/0001-90")]
    r = analisar_auditoria(txs)
    assert abs(r.retencao_estimada - 615.0) < 1.0


def test_heatmap_e_serializacao_json():
    txs = [_tx("2026-01-10", -100, memo="TARIFA MANUTENCAO CONTA")]
    r = analisar_auditoria(txs)
    assert set(r.heatmap) == {"CRITICO", "ALTO", "MEDIO", "BAIXO"}
    assert r.heatmap["BAIXO"]["qtd"] >= 1
    d = resumo_para_dict(r)
    assert d["regime"]["classe"] in ("COMPATIVEL", "ATENCAO", "ALTO", "CRITICO")
    assert "heatmap" in d and "sinais" in d and "top_disposicoes" in d


def test_sem_transacoes_nao_explode():
    r = analisar_auditoria([])
    assert r.n_transacoes == 0
    assert r.regime.multiplo_do_teto == 0.0
    assert r.regime.classe == "COMPATIVEL"


def test_cnpjs_das_transacoes_unicos():
    from api.matchers.auditoria_forense import cnpjs_das_transacoes
    txs = [
        _tx("2026-01-01", -1, nome="A 12.345.678/0001-90"),
        _tx("2026-01-02", -1, nome="B 12.345.678/0001-90"),
        _tx("2026-01-03", -1, nome="SEM CNPJ AQUI"),
    ]
    assert cnpjs_das_transacoes(txs) == ["12345678000190"]


def test_construir_cadastro_do_cache_liga_pos_baixa():
    from api.matchers.auditoria_forense import construir_cadastro
    cnpj = "63567345000141"
    cache = {cnpj: {"situacao": "BAIXADA", "data_situacao": "2026-03-11", "porte": "DEMAIS"}}
    txs = [_tx("2026-05-13", -10_000, nome="PG 63.567.345/0001-41")]
    cadastro = construir_cadastro(txs, cache=cache)
    assert cadastro.get(cnpj, {}).get("situacao") == "BAIXADA"
    # com o cadastro montado do cache, a auditoria liga pós-baixa
    r = analisar_auditoria(txs, cadastro=cadastro)
    assert r.pos_baixa_qtd == 1
