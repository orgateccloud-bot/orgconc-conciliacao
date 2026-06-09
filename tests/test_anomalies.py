"""Cobertura das regras de deteccao de anomalias em transacoes bancarias.

Modulo-alvo: api/parsers/anomalies.py — logica pura, sem DB/rede.

Cada regra e exercitada com entradas que DISPARAM e que NAO DISPARAM:
- _chave_transacao: chave com fitid vs. fallback memo
- _coletar_chaves_anomalas: duplicidade, valor alto, estorno, transferencia
  sem par e com par (casamento debito/credito entre contas)
- _detectar_anomalias: severidades, ramos condicionais e ordenacao
"""
from __future__ import annotations

from api.parsers.anomalies import (
    _chave_transacao,
    _coletar_chaves_anomalas,
    _detectar_anomalias,
)
from api.parsers.constants import (
    LIMITE_VALOR_ALTO,
    LIMITE_VALOR_CRITICO,
)


# ── helpers (espelham o estilo de tests/test_api.py) ──────────────────────


def _tx(
    valor: float,
    memo: str = "TESTE",
    data: str = "2026-04-15",
    nome: str = "",
    fitid: str | None = None,
) -> dict:
    t = {
        "valor": valor,
        "memo": memo,
        "nome": nome,
        "data": data,
        "tipo": "DEBIT",
        "conta": "",
    }
    if fitid is not None:
        t["fitid"] = fitid
    return t


def _extrato(txs: list[dict], conta: str = "AG 0000 / CC 0000") -> dict:
    return {"conta": conta, "qtd": len(txs), "transacoes": txs, "arquivo": "test.ofx"}


# ── _chave_transacao ──────────────────────────────────────────────────────


def test_chave_transacao_usa_fitid_quando_disponivel():
    t = _tx(123.456, memo="QUALQUER", data="2026-01-02", fitid="FIT-001")
    chave = _chave_transacao("Conta X", t)
    assert chave == ("Conta X", "2026-01-02", 123.46, "FIT-001")


def test_chave_transacao_fallback_memo_quando_fitid_vazio():
    t = _tx(99.999, memo="MEMO LONGO " * 10, data="2026-01-02", fitid="")
    chave = _chave_transacao("Conta X", t)
    # fitid vazio -> usa memo truncado em 40 chars
    assert chave[0] == "Conta X"
    assert chave[1] == "2026-01-02"
    assert chave[2] == 100.0  # arredondado a 2 casas
    assert chave[3] == ("MEMO LONGO " * 10)[:40]
    assert len(chave[3]) == 40


def test_chave_transacao_fallback_memo_quando_sem_fitid_e_sem_memo():
    # sem chave fitid e sem memo -> memo vira "" via (t.get("memo") or "")
    t = {"valor": 10.0, "data": "2026-03-03", "memo": None}
    chave = _chave_transacao("Conta Y", t)
    assert chave == ("Conta Y", "2026-03-03", 10.0, "")


# ── _coletar_chaves_anomalas: duplicidade ─────────────────────────────────


def test_coletar_duplicidade_marca_ambas_as_transacoes():
    t1 = _tx(100.0, "PIX RECEBIDO", "2026-04-15", fitid="A1")
    t2 = _tx(100.0, "PIX RECEBIDO", "2026-04-15", fitid="A2")
    chaves = _coletar_chaves_anomalas([_extrato([t1, t2], "Conta A")])
    assert _chave_transacao("Conta A", t1) in chaves
    assert _chave_transacao("Conta A", t2) in chaves


def test_coletar_sem_duplicidade_nao_marca():
    # transacoes distintas (memos diferentes) e valores baixos -> nada marcado
    t1 = _tx(100.0, "PIX RECEBIDO A", "2026-04-15", fitid="A1")
    t2 = _tx(200.0, "PIX RECEBIDO B", "2026-04-15", fitid="A2")
    chaves = _coletar_chaves_anomalas([_extrato([t1, t2], "Conta A")])
    assert chaves == set()


# ── _coletar_chaves_anomalas: valor alto ──────────────────────────────────


def test_coletar_valor_acima_do_limite_alto_marca():
    t = _tx(LIMITE_VALOR_ALTO + 1, "TED GRANDE", fitid="V1")
    chaves = _coletar_chaves_anomalas([_extrato([t], "Conta A")])
    assert _chave_transacao("Conta A", t) in chaves


def test_coletar_valor_negativo_alto_marca_via_abs():
    t = _tx(-(LIMITE_VALOR_ALTO + 50), "DEBITO GRANDE", fitid="V2")
    chaves = _coletar_chaves_anomalas([_extrato([t], "Conta A")])
    assert _chave_transacao("Conta A", t) in chaves


def test_coletar_valor_exatamente_no_limite_nao_marca():
    # estritamente maior (>) — exatamente no limite NAO dispara
    t = _tx(LIMITE_VALOR_ALTO, "NO LIMITE", fitid="V3")
    chaves = _coletar_chaves_anomalas([_extrato([t], "Conta A")])
    assert chaves == set()


# ── _coletar_chaves_anomalas: estorno ─────────────────────────────────────


def test_coletar_estorno_no_memo_marca():
    t = _tx(50.0, "ESTORNO TARIFA", fitid="E1")
    chaves = _coletar_chaves_anomalas([_extrato([t], "Conta A")])
    assert _chave_transacao("Conta A", t) in chaves


def test_coletar_estorno_no_nome_marca():
    # palavra de estorno vem do campo nome, nao do memo
    t = _tx(50.0, memo="PAGAMENTO", nome="DEVOLUCAO CLIENTE", fitid="E2")
    chaves = _coletar_chaves_anomalas([_extrato([t], "Conta A")])
    assert _chave_transacao("Conta A", t) in chaves


def test_coletar_sem_estorno_nao_marca():
    t = _tx(50.0, memo="PAGAMENTO NORMAL", nome="FORNECEDOR", fitid="E3")
    chaves = _coletar_chaves_anomalas([_extrato([t], "Conta A")])
    assert chaves == set()


# ── _coletar_chaves_anomalas: transferencia entre contas ──────────────────


def test_coletar_transferencia_com_par_nao_marca():
    # debito numa conta + credito de mesmo valor noutra = par casado, nao marca
    saida = _tx(-1000.0, "INTERCREDIS TRANSF MESMA TIT", fitid="T1")
    entrada = _tx(1000.0, "INTERCREDIS TRANSF MESMA TIT", fitid="T2")
    e1 = _extrato([saida], "Conta A")
    e2 = _extrato([entrada], "Conta B")
    chaves = _coletar_chaves_anomalas([e1, e2])
    # par casado -> nenhuma das duas e marcada por transferencia.
    # (valores < limite alto, sem estorno, sem duplicidade)
    assert chaves == set()


def test_coletar_transferencia_sem_par_marca_ambos_os_lados():
    # valores diferentes -> nao casam -> ambos marcados
    saida = _tx(-1000.0, "INTERCREDIS TRANSF MESMA TIT", fitid="T1")
    entrada = _tx(500.0, "INTERCREDIS TRANSF MESMA TIT", fitid="T2")
    e1 = _extrato([saida], "Conta A")
    e2 = _extrato([entrada], "Conta B")
    chaves = _coletar_chaves_anomalas([e1, e2])
    assert _chave_transacao("Conta A", saida) in chaves
    assert _chave_transacao("Conta B", entrada) in chaves


def test_coletar_transferencia_mesmo_sinal_nao_casa():
    # mesmo valor absoluto mas mesmo sinal (produto > 0) -> nao casa -> marca
    t1 = _tx(-1000.0, "TRANSF.CONTAS", fitid="T1")
    t2 = _tx(-1000.0, "TRANSF.CONTAS", fitid="T2")
    e1 = _extrato([t1], "Conta A")
    e2 = _extrato([t2], "Conta B")
    chaves = _coletar_chaves_anomalas([e1, e2])
    assert _chave_transacao("Conta A", t1) in chaves
    assert _chave_transacao("Conta B", t2) in chaves


def test_coletar_transferencia_credito_extra_sem_par_no_lado_c2():
    # 1 saida casa com 1 entrada; sobra uma entrada extra em c2 sem par
    saida = _tx(-1000.0, "TRANSFERENCIA ENTRE CONTAS", fitid="T1")
    entrada_par = _tx(1000.0, "TRANSFERENCIA ENTRE CONTAS", fitid="T2")
    entrada_extra = _tx(2000.0, "TRANSFERENCIA ENTRE CONTAS", fitid="T3")
    e1 = _extrato([saida], "Conta A")
    e2 = _extrato([entrada_par, entrada_extra], "Conta B")
    chaves = _coletar_chaves_anomalas([e1, e2])
    # o par (saida/entrada_par) nao deve ser marcado por transferencia;
    # a entrada_extra (valor 2000 < limite) deve ser marcada (loop final j not in usados)
    assert _chave_transacao("Conta B", entrada_extra) in chaves
    # saida casada nao marcada
    assert _chave_transacao("Conta A", saida) not in chaves


def test_coletar_transferencia_revisita_indice_ja_usado():
    # Dois debitos em c1 e uma unica entrada em c2: o 1o debito casa (usa j=0),
    # o 2o debito reentra no loop e pula j=0 (linha `if j in usados: continue`).
    # memos distintos para nao disparar a regra de duplicidade — assim so a
    # logica de transferencia decide o que e marcado.
    saida1 = _tx(-1000.0, "TRANSF.CONTAS PRIMEIRA", fitid="T1")
    saida2 = _tx(-1000.0, "TRANSF.CONTAS SEGUNDA", fitid="T2")
    entrada = _tx(1000.0, "TRANSF.CONTAS UNICA", fitid="T3")
    e1 = _extrato([saida1, saida2], "Conta A")
    e2 = _extrato([entrada], "Conta B")
    chaves = _coletar_chaves_anomalas([e1, e2])
    # saida1 casa (nao marcada); saida2 fica sem par (marcada); entrada casada (nao).
    # Exatamente uma das duas saidas e marcada.
    marcadas = {
        _chave_transacao("Conta A", saida1) in chaves,
        _chave_transacao("Conta A", saida2) in chaves,
    }
    assert marcadas == {True, False}  # uma casou, a outra ficou sem par
    assert _chave_transacao("Conta B", entrada) not in chaves


def test_coletar_extrato_unico_nao_roda_transferencia():
    # len(extratos) < 2 -> ramo de transferencia nunca executa
    t = _tx(-1000.0, "INTERCREDIS TRANSF MESMA TIT", fitid="T1")
    chaves = _coletar_chaves_anomalas([_extrato([t], "Conta A")])
    assert chaves == set()


def test_coletar_lista_vazia_retorna_set_vazio():
    assert _coletar_chaves_anomalas([]) == set()


# ── _detectar_anomalias: duplicidade (alerta vs critico) ──────────────────


def test_detectar_duplicidade_2x_e_alerta():
    txs = [_tx(100.0, "TARIFA", "2026-04-15"), _tx(100.0, "TARIFA", "2026-04-15")]
    anomalias = _detectar_anomalias([_extrato(txs)])
    dups = [a for a in anomalias if a["tipo"] == "Duplicidade"]
    assert len(dups) == 1
    assert dups[0]["severidade"] == "alerta"
    assert "2x" in dups[0]["titulo"]


def test_detectar_duplicidade_3x_e_critico():
    txs = [_tx(100.0, "TARIFA", "2026-04-15") for _ in range(3)]
    anomalias = _detectar_anomalias([_extrato(txs)])
    dups = [a for a in anomalias if a["tipo"] == "Duplicidade"]
    assert len(dups) == 1
    assert dups[0]["severidade"] == "critico"
    assert dups[0]["valor"] == 100.0


# ── _detectar_anomalias: valor alto (atencao vs alerta) ───────────────────


def test_detectar_valor_critico_gera_alerta():
    txs = [_tx(LIMITE_VALOR_CRITICO + 1, "TED ENORME")]
    anomalias = _detectar_anomalias([_extrato(txs)])
    altos = [a for a in anomalias if a["tipo"] == "Valor alto"]
    assert len(altos) == 1
    assert altos[0]["severidade"] == "alerta"


def test_detectar_valor_alto_gera_atencao():
    txs = [_tx(LIMITE_VALOR_ALTO + 1, "TED MEDIO")]
    anomalias = _detectar_anomalias([_extrato(txs)])
    altos = [a for a in anomalias if a["tipo"] == "Valor alto"]
    assert len(altos) == 1
    assert altos[0]["severidade"] == "atencao"


def test_detectar_valor_no_limite_nao_gera_anomalia():
    txs = [_tx(LIMITE_VALOR_ALTO, "NO LIMITE")]
    anomalias = _detectar_anomalias([_extrato(txs)])
    altos = [a for a in anomalias if a["tipo"] == "Valor alto"]
    assert altos == []


def test_detectar_valor_alto_usa_nome_quando_memo_vazio():
    # memo vazio -> detalhe usa nome (cobre o ramo `t["memo"] or t["nome"]`)
    txs = [_tx(LIMITE_VALOR_ALTO + 5, memo="", nome="CLIENTE GIGANTE")]
    anomalias = _detectar_anomalias([_extrato(txs)])
    altos = [a for a in anomalias if a["tipo"] == "Valor alto"]
    assert len(altos) == 1
    assert "CLIENTE GIGANTE" in altos[0]["detalhe"]


# ── _detectar_anomalias: estorno ──────────────────────────────────────────


def test_detectar_estorno_critico():
    txs = [_tx(200.0, "ESTORNO INDEVIDO")]
    anomalias = _detectar_anomalias([_extrato(txs)])
    estornos = [a for a in anomalias if a["tipo"] == "Estorno"]
    assert len(estornos) == 1
    assert estornos[0]["severidade"] == "critico"


def test_detectar_sem_estorno():
    txs = [_tx(200.0, "PAGAMENTO COMUM")]
    anomalias = _detectar_anomalias([_extrato(txs)])
    assert [a for a in anomalias if a["tipo"] == "Estorno"] == []


# ── _detectar_anomalias: transferencia entre contas ───────────────────────


def test_detectar_transferencia_sem_par():
    e1 = _extrato([_tx(-1000.0, "INTERCREDIS TRANSF MESMA TIT")], "Conta A")
    e2 = _extrato([_tx(-500.0, "INTERCREDIS TRANSF MESMA TIT")], "Conta B")
    anomalias = _detectar_anomalias([e1, e2])
    sp = [a for a in anomalias if a["tipo"] == "Transferencia sem par"]
    assert len(sp) == 1
    assert sp[0]["severidade"] == "alerta"
    assert "Conta A" in sp[0]["conta"] and "Conta B" in sp[0]["conta"]


def test_detectar_transferencia_com_par_nao_gera_anomalia():
    # debito -1000 casa com credito +1000 -> sem_par == 0 -> nada
    e1 = _extrato([_tx(-1000.0, "INTERCREDIS TRANSF MESMA TIT")], "Conta A")
    e2 = _extrato([_tx(1000.0, "INTERCREDIS TRANSF MESMA TIT")], "Conta B")
    anomalias = _detectar_anomalias([e1, e2])
    assert [a for a in anomalias if a["tipo"] == "Transferencia sem par"] == []


def test_detectar_transferencia_par_completo_com_extra_sem_par():
    # cobre o `break` apos casar (linha 144-146) E sem_par > 0 do extra
    e1 = _extrato([_tx(-1000.0, "TRANSF.CONTAS")], "Conta A")
    e2 = _extrato(
        [_tx(1000.0, "TRANSF.CONTAS"), _tx(3000.0, "TRANSF.CONTAS")], "Conta B"
    )
    anomalias = _detectar_anomalias([e1, e2])
    sp = [a for a in anomalias if a["tipo"] == "Transferencia sem par"]
    assert len(sp) == 1
    assert "1 sem par" in sp[0]["detalhe"]


def test_detectar_transferencia_revisita_indice_ja_usado():
    # Dois debitos casando contra uma unica entrada: o 2o debito reentra no
    # loop interno e pula o indice ja consumido (`if j in usados: continue`).
    e1 = _extrato(
        [_tx(-1000.0, "TRANSF.CONTAS"), _tx(-1000.0, "TRANSF.CONTAS")], "Conta A"
    )
    e2 = _extrato([_tx(1000.0, "TRANSF.CONTAS")], "Conta B")
    anomalias = _detectar_anomalias([e1, e2])
    sp = [a for a in anomalias if a["tipo"] == "Transferencia sem par"]
    # 1 par casa, sobra 1 debito sem par
    assert len(sp) == 1
    assert "1" in sp[0]["titulo"]


def test_detectar_sem_transferencia_extrato_unico():
    # apenas um extrato -> ramo de transferencia nao roda
    e1 = _extrato([_tx(-1000.0, "INTERCREDIS TRANSF MESMA TIT")], "Conta A")
    anomalias = _detectar_anomalias([e1])
    assert [a for a in anomalias if a["tipo"] == "Transferencia sem par"] == []


# ── _detectar_anomalias: lista vazia e ordenacao por severidade ───────────


def test_detectar_lista_vazia():
    assert _detectar_anomalias([]) == []


def test_detectar_ordenacao_critico_antes_de_atencao():
    # mistura: valor alto (atencao) + estorno (critico) + duplicidade (alerta)
    txs = [
        _tx(LIMITE_VALOR_ALTO + 1, "TED MEDIO", "2026-04-10"),  # atencao
        _tx(50.0, "ESTORNO X", "2026-04-11"),  # critico
        _tx(10.0, "TARIFA", "2026-04-12"),  # parte da dup
        _tx(10.0, "TARIFA", "2026-04-12"),  # parte da dup (alerta)
    ]
    anomalias = _detectar_anomalias([_extrato(txs)])
    sevs = [a["severidade"] for a in anomalias]
    # critico vem antes de alerta, que vem antes de atencao
    assert sevs.index("critico") < sevs.index("alerta")
    assert sevs.index("alerta") < sevs.index("atencao")


def test_detectar_ordenacao_mesma_severidade_por_valor_desc():
    # dois valores 'atencao' -> o de maior |valor| vem primeiro
    txs = [
        _tx(LIMITE_VALOR_ALTO + 100, "TED A", "2026-04-10"),
        _tx(LIMITE_VALOR_ALTO + 9000, "TED B", "2026-04-11"),
    ]
    anomalias = _detectar_anomalias([_extrato(txs)])
    altos = [a for a in anomalias if a["tipo"] == "Valor alto"]
    assert abs(altos[0]["valor"]) >= abs(altos[1]["valor"])
