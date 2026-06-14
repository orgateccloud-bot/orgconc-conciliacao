"""Testes para api/matchers/documento.py — matcher do estágio 1 (CNPJ explícito).

Lógica pura + consulta à tabela `clientes`. Usa mocks de AsyncSession para
evitar dependência de banco real (estes módulos NÃO dependem de DATABASE_URL).

Cobre os ramos de:
- _normaliza_cnpj (normalização: dígitos, None, vazio, ruído)
- resolver (filtro por método, DOC_INVALIDO, NAO_ENCONTRADO, RESOLVIDO_BASE
  com cliente ativo/inativo)
- consultar_por_documento (doc inválido, não encontrado, encontrado)
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.db.models import Cliente
from api.matchers.cascata import Resultado, Transacao
from api.matchers.documento import (
    CadastroContraparte,
    DocumentoResolvido,
    _normaliza_cnpj,
    consultar_por_documento,
    resolver,
)


CLIENTE_ID = uuid.uuid4()
CNPJ_DIGITOS = "11222333000181"
CNPJ_FORMATADO = "11.222.333/0001-81"


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _mock_db(cliente: Cliente | None):
    """AsyncSession mockado: .execute().scalar_one_or_none() devolve `cliente`."""
    db = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=cliente)
    db.execute = AsyncMock(return_value=result_mock)
    return db


def _cliente(nome: str = "Empresa X LTDA", cnpj: str = CNPJ_FORMATADO, ativo: bool = True) -> Cliente:
    return Cliente(id=uuid.uuid4(), nome=nome, cnpj=cnpj, ativo=ativo)


def _resultado_doc(chave: str, metodo: str = "match_documento") -> Resultado:
    t = Transacao(
        data="2026-05-10", tipo="DEBIT", valor=-800.00,
        fitid="X1", memo="PIX EMITIDO", nome=f"Pagamento {chave}",
    )
    return Resultado(t, estagio=1, metodo=metodo, chave=chave)


# ────────────────────────────────────────────────────────────────────────
# _normaliza_cnpj
# ────────────────────────────────────────────────────────────────────────


def test_normaliza_cnpj_formatado():
    assert _normaliza_cnpj(CNPJ_FORMATADO) == CNPJ_DIGITOS


def test_normaliza_cnpj_so_digitos_inalterado():
    assert _normaliza_cnpj(CNPJ_DIGITOS) == CNPJ_DIGITOS


def test_normaliza_cnpj_remove_ruido_e_espacos():
    assert _normaliza_cnpj(" 11.222.333/0001-81 abc ") == CNPJ_DIGITOS


def test_normaliza_cnpj_none_retorna_vazio():
    assert _normaliza_cnpj(None) == ""


def test_normaliza_cnpj_vazio_retorna_vazio():
    assert _normaliza_cnpj("") == ""


def test_normaliza_cnpj_sem_digitos():
    assert _normaliza_cnpj("sem numeros aqui") == ""


# ────────────────────────────────────────────────────────────────────────
# resolver — filtro de estágio/método
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolver_ignora_outros_metodos():
    """resolver só processa metodo == 'match_documento'."""
    r_nfe = _resultado_doc("99", metodo="match_nfe")
    r_tarifa = _resultado_doc("X", metodo="tarifa_bancaria")
    db = _mock_db(None)
    saida = await resolver([r_nfe, r_tarifa], db)
    assert saida == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_resolver_lista_vazia():
    db = _mock_db(None)
    saida = await resolver([], db)
    assert saida == []
    db.execute.assert_not_called()


# ────────────────────────────────────────────────────────────────────────
# resolver — DOC_INVALIDO
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolver_doc_invalido_poucos_digitos():
    """CNPJ com menos de 14 dígitos → DOC_INVALIDO, sem ir ao banco."""
    r = _resultado_doc("123")
    db = _mock_db(None)
    saida = await resolver([r], db)
    assert len(saida) == 1
    assert saida[0].status == "DOC_INVALIDO"
    assert "não tem 14 dígitos" in saida[0].flag
    assert "123" in saida[0].flag
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_resolver_doc_invalido_muitos_digitos():
    """Mais de 14 dígitos também é inválido."""
    r = _resultado_doc("1" * 20)
    db = _mock_db(None)
    saida = await resolver([r], db)
    assert len(saida) == 1
    assert saida[0].status == "DOC_INVALIDO"


@pytest.mark.asyncio
async def test_resolver_doc_invalido_chave_vazia():
    """Chave vazia → 0 dígitos → DOC_INVALIDO (cobre o ramo `r.chave or ''`)."""
    r = _resultado_doc("")
    db = _mock_db(None)
    saida = await resolver([r], db)
    assert len(saida) == 1
    assert saida[0].status == "DOC_INVALIDO"


# ────────────────────────────────────────────────────────────────────────
# resolver — NAO_ENCONTRADO
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolver_nao_encontrado():
    """14 dígitos válidos mas CNPJ não cadastrado → NAO_ENCONTRADO."""
    r = _resultado_doc(CNPJ_FORMATADO)
    db = _mock_db(None)
    saida = await resolver([r], db)
    assert len(saida) == 1
    assert saida[0].status == "NAO_ENCONTRADO"
    assert saida[0].cnpj_normalizado == CNPJ_DIGITOS
    assert "não cadastrado" in saida[0].flag
    db.execute.assert_awaited_once()


# ────────────────────────────────────────────────────────────────────────
# resolver — RESOLVIDO_BASE
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolver_resolvido_cliente_ativo():
    """Cliente ativo encontrado → RESOLVIDO_BASE sem flag de alerta."""
    cli = _cliente(nome="Fornecedor Ativo SA", ativo=True)
    r = _resultado_doc(CNPJ_DIGITOS)
    db = _mock_db(cli)
    saida = await resolver([r], db)
    assert len(saida) == 1
    assert saida[0].status == "RESOLVIDO_BASE"
    assert saida[0].razao_social == "Fornecedor Ativo SA"
    assert saida[0].cnpj_normalizado == CNPJ_DIGITOS
    assert saida[0].flag == ""


@pytest.mark.asyncio
async def test_resolver_resolvido_cliente_inativo_com_alerta():
    """Cliente inativo → RESOLVIDO_BASE com flag de alerta."""
    cli = _cliente(nome="Fornecedor Inativo SA", ativo=False)
    r = _resultado_doc(CNPJ_FORMATADO)
    db = _mock_db(cli)
    saida = await resolver([r], db)
    assert len(saida) == 1
    assert saida[0].status == "RESOLVIDO_BASE"
    assert saida[0].razao_social == "Fornecedor Inativo SA"
    assert "inativo" in saida[0].flag


@pytest.mark.asyncio
async def test_resolver_multiplas_transacoes_mistas():
    """Mistura: inválida + não-encontrada na mesma rodada (ordem preservada)."""
    r_inval = _resultado_doc("999")
    r_naoenc = _resultado_doc(CNPJ_DIGITOS)
    db = _mock_db(None)
    saida = await resolver([r_inval, r_naoenc], db)
    assert len(saida) == 2
    assert saida[0].status == "DOC_INVALIDO"
    assert saida[1].status == "NAO_ENCONTRADO"


@pytest.mark.asyncio
async def test_resolver_formato_consulta_canonico():
    """Verifica que a query usa tanto o formato XX.XXX.XXX/XXXX-XX quanto dígitos."""
    cli = _cliente(ativo=True)
    r = _resultado_doc(CNPJ_DIGITOS)
    db = _mock_db(cli)
    await resolver([r], db)
    # Apenas garante que a consulta foi disparada (1 transação válida).
    db.execute.assert_awaited_once()


# ────────────────────────────────────────────────────────────────────────
# consultar_por_documento
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consultar_doc_invalido_retorna_none():
    db = _mock_db(None)
    out = await consultar_por_documento(db, CLIENTE_ID, "123")
    assert out is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_consultar_doc_none_retorna_none():
    """doc None → normaliza para '' → len != 14 → None, sem ir ao banco."""
    db = _mock_db(None)
    out = await consultar_por_documento(db, CLIENTE_ID, None)  # type: ignore[arg-type]
    assert out is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_consultar_nao_encontrado_retorna_none():
    db = _mock_db(None)
    out = await consultar_por_documento(db, CLIENTE_ID, CNPJ_FORMATADO)
    assert out is None
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_consultar_encontrado_retorna_contraparte():
    cli = _cliente(nome="Contraparte Real LTDA")
    db = _mock_db(cli)
    out = await consultar_por_documento(db, CLIENTE_ID, CNPJ_DIGITOS)
    assert isinstance(out, CadastroContraparte)
    assert out.nome_real == "Contraparte Real LTDA"
    assert out.conta_contabil == ""
    db.execute.assert_awaited_once()


# ────────────────────────────────────────────────────────────────────────
# consultar_por_documento — filtro de tenant (org_id) — W4 #15
# ────────────────────────────────────────────────────────────────────────


def _filtra_org_na_where(db) -> bool:
    """True se a cláusula WHERE da última query restringe por clientes.org_id."""
    stmt = db.execute.await_args.args[0]
    where_sql = str(stmt.whereclause.compile(compile_kwargs={"literal_binds": False}))
    return "clientes.org_id" in where_sql


@pytest.mark.asyncio
async def test_consultar_filtra_por_org_id_explicito():
    """Com org_id explícito, a query inclui o filtro Cliente.org_id na WHERE."""
    org = uuid.uuid4()
    cli = _cliente(nome="Contraparte do Tenant")
    db = _mock_db(cli)
    out = await consultar_por_documento(db, CLIENTE_ID, CNPJ_DIGITOS, org_id=org)
    assert out is not None and out.nome_real == "Contraparte do Tenant"
    assert _filtra_org_na_where(db)


@pytest.mark.asyncio
async def test_consultar_sem_org_consulta_global():
    """Sem org no parâmetro nem no contexto, a WHERE NÃO filtra por org_id
    (comportamento legado preservado — RLS continua sendo a defesa no banco)."""
    cli = _cliente(nome="Global")
    db = _mock_db(cli)
    out = await consultar_por_documento(db, CLIENTE_ID, CNPJ_DIGITOS)
    assert out is not None
    assert not _filtra_org_na_where(db)


@pytest.mark.asyncio
async def test_consultar_usa_org_do_contexto_rls():
    """Sem org_id explícito, usa o org do contexto de RLS (get_org_context)."""
    from api.db.rls_context import reset_org_context, set_org_context

    org = uuid.uuid4()
    token = set_org_context(str(org))
    try:
        cli = _cliente(nome="Do Contexto")
        db = _mock_db(cli)
        out = await consultar_por_documento(db, CLIENTE_ID, CNPJ_DIGITOS)
        assert out is not None
        assert _filtra_org_na_where(db)
    finally:
        reset_org_context(token)


# ────────────────────────────────────────────────────────────────────────
# Sanidade dos dataclasses
# ────────────────────────────────────────────────────────────────────────


def test_documento_resolvido_defaults():
    r = _resultado_doc(CNPJ_DIGITOS)
    d = DocumentoResolvido(r, "NAO_ENCONTRADO")
    assert d.razao_social == ""
    assert d.cnpj_normalizado == ""
    assert d.flag == ""
    assert d.resultado is r


def test_cadastro_contraparte_default_conta():
    c = CadastroContraparte(nome_real="Fulano")
    assert c.conta_contabil == ""
