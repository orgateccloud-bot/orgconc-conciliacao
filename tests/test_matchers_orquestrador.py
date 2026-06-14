"""Testes do orquestrador da cascata completa.

Simula o cenário do relatorio_completo.csv do OrgNeural2: 11 transações
distribuídas pelos 6 estágios, esperando 9 automatizadas (~81,8%).
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.db.models import Cliente, Contrato, GuiaTributo
from api.matchers.cascata import Disposicao, Transacao, classificar
from api.matchers.orquestrador import conciliar, taxa_automatizacao


CLIENTE_ID = uuid.uuid4()


def _mock_db(query_results: dict[type, list]):
    """Mocka AsyncSession para retornar conjuntos diferentes conforme o modelo consultado.

    `query_results` é um dict {ModeloSQL: lista_de_objetos_a_retornar}.
    """
    db = MagicMock()

    async def fake_execute(stmt):
        result = MagicMock()
        # Inspeciona o nome do modelo na cláusula FROM do statement
        try:
            from_obj = stmt.get_final_froms()[0]
            tabela = from_obj.name
        except Exception:  # noqa: BLE001
            tabela = ""

        mapping = {
            "clientes": query_results.get(Cliente, []),
            "guia_tributo": query_results.get(GuiaTributo, []),
            "contrato": query_results.get(Contrato, []),
        }
        linhas = mapping.get(tabela, [])

        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=linhas)
        # scalar_one_or_none retorna o primeiro elemento ou None
        primeiro = linhas[0] if linhas else None
        result.scalars = MagicMock(return_value=scalars_mock)
        result.scalar_one_or_none = MagicMock(return_value=primeiro)
        return result

    db.execute = AsyncMock(side_effect=fake_execute)
    return db


def _t(memo: str, nome: str, valor: float, fitid: str, tipo: str = "DEBIT") -> Transacao:
    return Transacao(
        data="2026-05-10", tipo=tipo, valor=-abs(valor) if tipo == "DEBIT" else abs(valor),
        fitid=fitid, memo=memo, nome=nome,
    )


# Espelha as 11 transações do relatorio_completo.csv original
_TRANSACOES_EXEMPLO = [
    _t("PIX EMITIDO OUTRA IF", "Pagamento Pix 64.961.274/0001-91", 1500.00, "X432935"),
    _t("PIX EMITIDO OUTRA IF", "Pagamento Pix 11.222.333/0001-81", 800.00, "X296671"),
    _t("DEB.TIT.COMPE EFETIVADO", "Rsf7j94 nf 52269", 185.73, "X296461"),
    _t("DEB.TIT.COMPE EFETIVADO", "RMB4A64 NF 2447 3 3", 2000.00, "X706617"),
    _t("DEB.TIT.COMPE EFETIVADO", "XPTO nf 88888", 999.00, "X753316"),  # NF ausente
    _t("TARIFA COBRANCA", "", 4.40, "X116221"),
    _t("DARF PAGAMENTO", "DARF PARCELAMENTO DIFAL", 1234.56, "X96508"),
    _t("DEB.CONV.SEGUROS", "Seguro mensal", 780.00, "X946122"),
    _t("DEB.TRANSF.CONTAS DIFERENTE", "FAV.: JOAO SILVA SERVICOS", 8000.00, "X433434"),
    _t("DEB.TRANSF.CONTAS DIFERENTE", "FAV.: FULANO DESCONHECIDO", 150.00, "X768994"),
    _t("DEB.TRANSF.CONTAS MESMA TIT", "FAV.: PROPRIO CLIENTE", 2000.00, "X106834"),
]


@pytest.mark.asyncio
async def test_cascata_completa_relatorio_exemplo():
    """Reproduz o cenário do relatorio_completo.csv:
    - 9 automatizadas (1500, 800, 185.73, 2000, 4.40, 1234.56, 780.00, 8000, 2000-interno)
    - 2 pendentes (999 sem NF, 150 sem alias)
    """
    # Cadastros conhecidos:
    cliente1 = Cliente(id=uuid.uuid4(), nome="Empresa Alfa LTDA",
                       cnpj="64.961.274/0001-91", ativo=True, plano="basico")
    cliente2 = Cliente(id=uuid.uuid4(), nome="JOAO SILVA SERVICOS ME",
                       cnpj="22.333.444/0001-95", ativo=True, plano="basico")
    cliente_pix2 = Cliente(id=uuid.uuid4(), nome="Empresa Beta SA",
                           cnpj="11.222.333/0001-81", ativo=True, plano="basico")

    guia_darf = GuiaTributo(id=uuid.uuid4(), cliente_id=CLIENTE_ID, tipo="DARF",
                            valor=Decimal("1234.56"), ativo=True,
                            competencia="2026-04", conta_contabil="2.1.3.01")
    contrato_seguro = Contrato(id=uuid.uuid4(), cliente_id=CLIENTE_ID,
                               descricao="Seguro frota", valor=Decimal("780.00"),
                               padrao_memo="SEGURO", ativo=True,
                               conta_contabil="3.1.2.04")

    # Mock db por tabela (filtra contrato/guia pelo valor extraído do SQL)
    import re as _re
    db = MagicMock()

    def _extrair_valor(stmt_str: str) -> float | None:
        """Extrai o valor numérico do WHERE abs(valor - X) <= 0.01."""
        m = _re.search(r"abs\([^)]*-\s*([0-9.]+)\)", stmt_str)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    async def fake_execute(stmt):
        result = MagicMock()
        try:
            tabela = stmt.get_final_froms()[0].name
        except Exception:  # noqa: BLE001
            tabela = ""
        stmt_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        if tabela == "clientes":
            normalized = stmt_str.replace(".", "").replace("/", "").replace("-", "")
            if "64961274000191" in normalized:
                linhas = [cliente1]
            elif "11222333000181" in normalized:
                linhas = [cliente_pix2]
            elif "JOAO SILVA" in stmt_str.upper():
                linhas = [cliente2]
            else:
                linhas = []
        elif tabela == "guia_tributo":
            valor = _extrair_valor(stmt_str)
            linhas = [guia_darf] if valor is not None and abs(valor - 1234.56) < 0.02 else []
        elif tabela == "contrato":
            valor = _extrair_valor(stmt_str)
            linhas = [contrato_seguro] if valor is not None and abs(valor - 780.00) < 0.02 else []
        else:
            linhas = []

        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=linhas)
        result.scalars = MagicMock(return_value=scalars_mock)
        result.scalar_one_or_none = MagicMock(return_value=linhas[0] if linhas else None)
        return result

    db.execute = AsyncMock(side_effect=fake_execute)

    # XMLs de NFe disponíveis (NF 52269 e 2447 batem; 88888 não)
    def _nfe_xml(numero: str, valor: str, emit: str) -> bytes:
        return f"""<?xml version="1.0"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe Id="NFe{numero.zfill(44)}">
    <ide><nNF>{numero}</nNF><serie>1</serie><dhEmi>2026-05-10T10:00:00-03:00</dhEmi></ide>
    <emit><CNPJ>12345678000190</CNPJ><xNome>{emit}</xNome></emit>
    <dest><CNPJ>11222333000181</CNPJ><xNome>Cliente</xNome></dest>
    <total><ICMSTot><vNF>{valor}</vNF></ICMSTot></total>
  </infNFe></NFe>
</nfeProc>""".encode("utf-8")

    xmls = [
        ("nf52269.xml", _nfe_xml("52269", "185.73", "Fornecedor Rsf7j94")),
        ("nf2447.xml", _nfe_xml("2447", "2000.00", "Fornecedor RMB4A64")),
    ]

    resultados = [classificar(t) for t in _TRANSACOES_EXEMPLO]
    disp = await conciliar(resultados, db, CLIENTE_ID, xmls)

    assert len(disp) == 11

    # Contagem por disposição
    contagem: dict[str, int] = {}
    for d in disp:
        contagem[d.disposicao] = contagem.get(d.disposicao, 0) + 1

    # Esperados (idealmente):
    # - RESOLVIDO_CADASTRO ou RESOLVIDO_BASE: pix 1500 + pix 800 + transf 8000 = 3
    # - RESOLVIDO_NFE: 185.73 + 2000.00 = 2
    # - TARIFA_BANCARIA: 4.40 = 1
    # - RESOLVIDO_GUIA: 1234.56 = 1
    # - RESOLVIDO_CONTRATO: 780.00 = 1
    # - TRANSFERENCIA_INTERNA: 2000 mesma tit = 1
    # Total automatizado: 9
    # - PENDENTE_REVISAO: NF 88888 = 1
    # - PENDENTE_FUZZY: 150 fulano desconhecido = 1
    # Total pendente: 2

    automatizadas = sum(
        c for k, c in contagem.items()
        if k.startswith("RESOLVIDO_") or k in ("TRANSFERENCIA_INTERNA", "TARIFA_BANCARIA")
    )
    pendentes = 11 - automatizadas

    # Critério de aceite do PR 3: 9 automatizadas, 2 pendentes
    assert automatizadas == 9, f"Esperado 9 automatizadas, obtido {automatizadas}: {contagem}"
    assert pendentes == 2, f"Esperado 2 pendentes, obtido {pendentes}: {contagem}"
    assert taxa_automatizacao(disp) == 81.8


@pytest.mark.asyncio
async def test_orquestrador_sem_xmls():
    """Sem XMLs, transações do estágio 2 viram PENDENTE_MATCHER."""
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        scalar_one_or_none=MagicMock(return_value=None),
    ))
    transacoes = [_t("DEB.TIT", "nf 99", 100.00, "X1")]
    resultados = [classificar(t) for t in transacoes]
    disp = await conciliar(resultados, db, CLIENTE_ID, xmls_nfe=None)
    assert disp[0].disposicao == "PENDENTE_MATCHER"
    assert "nenhum XML" in disp[0].flag


@pytest.mark.asyncio
async def test_taxa_automatizacao_calculo():
    """taxa_automatizacao retorna % correto."""
    t = _t("x", "", 1.0, "F1")
    disp = [
        Disposicao(t, 0, "TRANSFERENCIA_INTERNA"),
        Disposicao(t, 1, "RESOLVIDO_CADASTRO"),
        Disposicao(t, 2, "PENDENTE_REVISAO"),
        Disposicao(t, 3, "TARIFA_BANCARIA"),
    ]
    assert taxa_automatizacao(disp) == 75.0
    assert taxa_automatizacao([]) == 0.0


# ─────────────────────────────────────────────────────────────────────────
# W6 (#16): blindagem do enriquecimento CNPJ no request path
#   - timeout/erro de rede não pode derrubar a conciliação
#   - circuit breaker abre após N falhas e para de tentar no resto do lote
# ─────────────────────────────────────────────────────────────────────────

import httpx  # noqa: E402

from api.matchers import cnpj_enricher  # noqa: E402
from api.matchers.cnpj_enricher import CnpjCircuitBreaker, enriquecer_lote, enriquecer_um  # noqa: E402


@pytest.fixture
def _sem_sleep(monkeypatch):
    """Neutraliza os sleeps (rate limit + backoff) para o teste rodar rápido."""
    async def _noop(*_a, **_k):
        return None
    monkeypatch.setattr(cnpj_enricher.asyncio, "sleep", _noop)


@pytest.fixture
def _cache_em_memoria(monkeypatch):
    """Isola o cache (não toca o data/cnpj_cache.json real)."""
    monkeypatch.setattr(cnpj_enricher, "_carregar_cache", lambda: {})
    monkeypatch.setattr(cnpj_enricher, "_salvar_cache", lambda cache: None)


def _db_sem_schema_cnpj():
    """Mock de AsyncSession onde o schema cnpj.* NÃO existe (fallback RFB vazio)."""
    db = MagicMock()

    async def _execute(*_a, **_k):
        r = MagicMock()
        r.scalar = MagicMock(return_value=False)  # schema cnpj inexistente
        r.fetchone = MagicMock(return_value=None)
        r.fetchall = MagicMock(return_value=[])
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        r.scalars = MagicMock(return_value=scalars_mock)
        r.scalar_one_or_none = MagicMock(return_value=None)
        return r

    db.execute = AsyncMock(side_effect=_execute)
    return db


@pytest.mark.asyncio
async def test_conciliacao_completa_mesmo_com_brasilapi_em_timeout(
    _sem_sleep, _cache_em_memoria, monkeypatch
):
    """BrasilAPI sempre em timeout → conciliação completa SEM exceção,
    com os CNPJs marcados como não-enriquecidos (sem razão social da rede)."""
    chamadas = {"n": 0}

    async def _sempre_timeout(client, cnpj):
        chamadas["n"] += 1
        return cnpj_enricher._FALHA_REDE

    monkeypatch.setattr(cnpj_enricher, "_consulta_brasilapi", _sempre_timeout)

    # Sem cadastro/base: tudo cai em NAO_ENCONTRADO, mas a conciliação não falha.
    db = _db_sem_schema_cnpj()
    # As 2 primeiras transações de exemplo têm CNPJ no nome (PIX) → enriquecimento roda.
    transacoes = [
        _t("PIX EMITIDO OUTRA IF", "Pagamento Pix 64.961.274/0001-91", 1500.00, "X1"),
        _t("PIX EMITIDO OUTRA IF", "Pagamento Pix 11.222.333/0001-81", 800.00, "X2"),
    ]
    resultados = [classificar(t) for t in transacoes]

    # Não deve lançar exceção mesmo com a rede toda falhando.
    disp = await conciliar(resultados, db, CLIENTE_ID, xmls_nfe=None)

    assert len(disp) == 2
    # A rede foi tentada (não ficou em cache nem foi pulada de cara).
    assert chamadas["n"] >= 1
    # Nenhuma disposição ganhou razão social via BrasilAPI (não-enriquecidas).
    for d in disp:
        assert "BAIXADA" not in (d.flag or "")  # nenhum dado fresco aplicado


@pytest.mark.asyncio
async def test_circuit_breaker_abre_e_para_de_tentar_no_resto_do_lote(
    _sem_sleep, _cache_em_memoria, monkeypatch
):
    """Após N falhas de rede consecutivas o breaker abre e o RESTANTE do lote
    pula o BrasilAPI — número de chamadas de rede fica limitado pelo threshold."""
    threshold = 3
    monkeypatch.setenv("CNPJ_ENRICH_BREAKER_THRESHOLD", str(threshold))

    chamadas = {"n": 0}

    async def _sempre_timeout(client, cnpj):
        chamadas["n"] += 1
        return cnpj_enricher._FALHA_REDE

    monkeypatch.setattr(cnpj_enricher, "_consulta_brasilapi", _sempre_timeout)

    # Lote grande de CNPJs distintos e válidos.
    cnpjs = [f"{i:014d}" for i in range(1, 31)]
    # Concorrência 1 + sem sleep → ordem determinística, o breaker fecha cedo.
    resultados = await enriquecer_lote(cnpjs, db=None, max_concurrency=1)

    assert len(resultados) == len(cnpjs)
    # Todos sem enriquecer (fonte "erro": sem cache, sem rede, sem RFB local).
    assert all(info.fonte == "erro" for info in resultados.values())
    # O breaker limitou as tentativas de rede: no máximo threshold falhas
    # (mais até 2 retries do CNPJ que estourou o threshold). NÃO 30*3 = 90.
    assert chamadas["n"] <= threshold + 2, (
        f"breaker não conteve o lote: {chamadas['n']} chamadas de rede"
    )


@pytest.mark.asyncio
async def test_breaker_aberto_pula_brasilapi_e_usa_fallback_rfb(_sem_sleep, monkeypatch):
    """Com o circuito já aberto, enriquecer_um NÃO chama a rede e cai direto no RFB local."""
    chamadas = {"n": 0}

    async def _nao_deveria_ser_chamado(client, cnpj):
        chamadas["n"] += 1
        return cnpj_enricher._FALHA_REDE

    monkeypatch.setattr(cnpj_enricher, "_consulta_brasilapi", _nao_deveria_ser_chamado)

    breaker = CnpjCircuitBreaker(threshold=1)
    breaker.registrar_falha()  # abre imediatamente
    assert breaker.aberto

    client = httpx.AsyncClient()  # nunca usado de fato
    try:
        info = await enriquecer_um(
            "12345678000190", cache={}, client=client, db=None, breaker=breaker
        )
    finally:
        await client.aclose()

    assert chamadas["n"] == 0  # rede nunca tocada com o circuito aberto
    assert info.fonte == "erro"


@pytest.mark.asyncio
async def test_404_nao_conta_para_o_breaker(_sem_sleep, monkeypatch):
    """404 (CNPJ não encontrado) é resposta válida da rede — não abre o breaker
    e reseta o contador de falhas."""
    breaker = CnpjCircuitBreaker(threshold=2)
    breaker.registrar_falha()  # 1 falha acumulada

    async def _retorna_404(client, cnpj):
        return cnpj_enricher.CnpjInfo(cnpj=cnpj, fonte="brasilapi", flag="CNPJ nao encontrado")

    monkeypatch.setattr(cnpj_enricher, "_consulta_brasilapi", _retorna_404)

    client = httpx.AsyncClient()
    try:
        info = await enriquecer_um(
            "12345678000190", cache={}, client=client, db=None, breaker=breaker
        )
    finally:
        await client.aclose()

    assert info.fonte == "brasilapi"
    assert not breaker.aberto
    # Sucesso reseta o contador → outra falha sozinha não abre (threshold 2).
    breaker.registrar_falha()
    assert not breaker.aberto


@pytest.mark.asyncio
async def test_timeout_explicito_configurado_no_client():
    """O AsyncClient do enriquecimento usa timeout explícito (connect + read)."""
    t = cnpj_enricher._enrich_timeout()
    assert isinstance(t, httpx.Timeout)
    assert t.read is not None and t.read > 0
    assert t.connect is not None and t.connect > 0
