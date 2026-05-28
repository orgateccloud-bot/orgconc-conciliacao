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
from api.matchers.cascata import Disposicao, Resultado, Transacao, classificar
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
    _t("DEB.TRANSF.CONTAS DIFERENTE", "FAV.: RENATO COSTA SERVICOS", 8000.00, "X433434"),
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
    cliente2 = Cliente(id=uuid.uuid4(), nome="RENATO COSTA SERVICOS ME",
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
            elif "RENATO COSTA" in stmt_str.upper():
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
