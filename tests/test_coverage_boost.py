"""Testes focados em elevar cobertura nos modulos com gap > 30%."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ORGCONC_DATA_DIR", str(Path(__file__).resolve().parent / "_data_test"))
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

# ── render.py ──────────────────────────────────────────────────────────────

def test_render_pdf_html_retorna_html_completo():
    from api.services.render import render_pdf_html
    extratos = [{"conta": "CC 001", "qtd": 3, "transacoes": [
        {"valor": 1000.0}, {"valor": -200.0}, {"valor": -50.0},
    ]}]
    anomalias = [
        {"severidade": "critico", "tipo": "Duplicidade", "titulo": "Dup", "conta": "CC 001", "valor": 100.0, "detalhe": "x"},
        {"severidade": "alerta", "tipo": "Atipica", "titulo": "Atip", "conta": "CC 001", "valor": 5000.0, "detalhe": "y"},
        {"severidade": "atencao", "tipo": "Outro", "titulo": "Outr", "conta": "CC 001", "valor": 1.0, "detalhe": "z"},
    ]
    html = render_pdf_html("# Relatorio\n\n## Resumo\n\nok.", anomalias, extratos, "rid-123")
    assert "<html" in html or "<!DOCTYPE" in html or "Relatorio" in html
    assert "ORGATEC" in html
    assert "rid-123" in html


def test_render_pdf_html_sem_transacoes():
    from api.services.render import render_pdf_html
    html = render_pdf_html("# Vazio", [], [], "rid-vazio")
    assert "ORGATEC" in html


# ── conciliacao_llm.py ─────────────────────────────────────────────────────

def test_get_api_key_sem_env_levanta_500():
    from fastapi import HTTPException
    from api.services.conciliacao_llm import get_api_key
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
        with pytest.raises(HTTPException) as exc:
            get_api_key()
    assert exc.value.status_code == 500


def test_get_api_key_com_env_retorna_chave():
    from api.services.conciliacao_llm import get_api_key
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}):
        key = get_api_key()
    assert key == "sk-ant-test-key"


def test_friendly_anthropic_error_credito():
    from api.services.conciliacao_llm import friendly_anthropic_error
    msg = friendly_anthropic_error("Your credit balance is zero.")
    assert "billing" in msg.lower() or "credito" in msg.lower()


def test_friendly_anthropic_error_rate_limit():
    from api.services.conciliacao_llm import friendly_anthropic_error
    msg = friendly_anthropic_error("rate limit exceeded")
    assert "rate" in msg.lower() or "aguarde" in msg.lower()


def test_friendly_anthropic_error_generico():
    from api.services.conciliacao_llm import friendly_anthropic_error
    msg = friendly_anthropic_error("internal server error")
    assert "internal server error" in msg


def test_sintetizar_consenso_sem_validos():
    from api.services.conciliacao_llm import sintetizar_consenso
    resultados = [{"erro": "timeout", "texto": ""}, {"erro": "err", "texto": ""}]
    texto, score, _custo, *_ = asyncio.run(sintetizar_consenso("key", resultados, 1000))
    assert score == 0.0
    assert "valido" in texto.lower() or texto


def test_sintetizar_consenso_um_valido():
    from api.services.conciliacao_llm import sintetizar_consenso
    resultados = [
        {"erro": None, "texto": "Relatorio A", "label": "Sonnet"},
        {"erro": "timeout", "texto": ""},
    ]
    texto, score, _custo, *_ = asyncio.run(sintetizar_consenso("key", resultados, 1000))
    assert texto == "Relatorio A"
    assert score == 0.5


def test_chamar_modelo_async_timeout():
    from api.services.conciliacao_llm import chamar_modelo_async, _LLM_TIMEOUT_S
    with patch("api.services.conciliacao_llm.asyncio.wait_for", side_effect=asyncio.TimeoutError):
        res = asyncio.run(chamar_modelo_async("key", "prompt", "claude-sonnet-4-6", "Sonnet", 100))
    assert res["erro"] == f"Timeout na API Claude ({_LLM_TIMEOUT_S:.0f}s)"
    assert res["texto"] == ""


def test_chamar_modelo_async_api_status_error():
    from api.services.conciliacao_llm import chamar_modelo_async
    from anthropic import APIStatusError
    import httpx
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(529, json={"error": {"message": "overloaded"}}, request=req)
    err = APIStatusError("overloaded", response=resp, body={"error": {"message": "overloaded"}})
    with patch("api.services.conciliacao_llm.asyncio.wait_for", side_effect=err):
        res = asyncio.run(chamar_modelo_async("key", "prompt", "claude-sonnet-4-6", "Sonnet", 100))
    assert res["erro"] is not None
    assert res["texto"] == ""


def test_chamar_modelo_async_sucesso():
    from api.services.conciliacao_llm import chamar_modelo_async

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = "Relatorio gerado."
    mock_resp = MagicMock()
    mock_resp.content = [mock_content]
    mock_resp.usage.input_tokens = 100
    mock_resp.usage.output_tokens = 50

    async def fake_wait_for(coro, timeout):
        return {"texto": "Relatorio gerado.", "input_tokens": 100, "output_tokens": 50}

    with patch("api.services.conciliacao_llm.asyncio.wait_for", side_effect=fake_wait_for):
        res = asyncio.run(chamar_modelo_async("key", "prompt", "claude-sonnet-4-6", "Sonnet", 4000))
    assert res["erro"] is None
    assert res["texto"] == "Relatorio gerado."
    assert res["modelo"] == "claude-sonnet-4-6"


# ── exports.py ─────────────────────────────────────────────────────────────

def test_block_url_fetcher_retorna_string_vazia():
    from api.routers.exports import _block_url_fetcher
    result = _block_url_fetcher("https://externo.com/recurso.css")
    assert result["string"] == b""
    assert result["mime_type"] == "text/plain"


def test_export_pdf_retorna_html_ou_pdf():
    """
    /export/pdf/{rid} deve retornar 200 com PDF ou HTML fallback.
    Em ambientes sem libs nativas do weasyprint, o fallback HTML eh acionado automaticamente.
    """
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)

    OFX = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKACCTFROM><ACCTID>9999</ACCTID></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260101</DTPOSTED><TRNAMT>100.00</TRNAMT><MEMO>Teste</MEMO></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    r = client.post("/conciliar/ofx?simular=true",
                    files=[("arquivos", ("t.ofx", OFX, "application/x-ofx"))])
    assert r.status_code == 200
    rid = r.json()["report_id"]

    r_pdf = client.get(f"/export/pdf/{rid}")
    assert r_pdf.status_code == 200
    ct = r_pdf.headers.get("content-type", "")
    # Aceita PDF ou HTML fallback
    assert "application/pdf" in ct or "text/html" in ct


def test_export_pdf_html_flag():
    """Com ?html=true, /export/pdf deve retornar HTML diretamente sem tentar PDF."""
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)

    OFX = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKACCTFROM><ACCTID>8888</ACCTID></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260102</DTPOSTED><TRNAMT>-50.00</TRNAMT><MEMO>Pagamento</MEMO></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    r = client.post("/conciliar/ofx?simular=true",
                    files=[("arquivos", ("t.ofx", OFX, "application/x-ofx"))])
    rid = r.json()["report_id"]

    r_html = client.get(f"/export/pdf/{rid}?html=true")
    assert r_html.status_code == 200
    assert "text/html" in r_html.headers.get("content-type", "")
    assert b"ORGATEC" in r_html.content


# ── db_persistence.py ─────────────────────────────────────────────────────

def test_salvar_no_banco_skip_quando_db_indisponivel():
    from api.services.db_persistence import salvar_no_banco
    with patch("api.services.db_persistence.DB_DISPONIVEL", False):
        result = asyncio.run(salvar_no_banco("rid-test", [], [], "simulacao_local"))
    assert result["status"] == "skip"
    assert "db_indisponivel" in result["motivo"]


def test_salvar_no_banco_error_em_excecao():
    from api.services.db_persistence import salvar_no_banco
    with patch("api.services.db_persistence.DB_DISPONIVEL", True), \
         patch("api.services.db_persistence.SessionLocal", side_effect=RuntimeError("fail")):
        result = asyncio.run(salvar_no_banco("rid-err", [], [], "simulacao_local"))
    assert result["status"] == "error"
    assert result["erro"] == "RuntimeError"


# ── health.py ─────────────────────────────────────────────────────────────

def test_health_com_db_erro():
    """Quando DB_DISPONIVEL=True mas query falha, banco_dados deve ser 'erro'."""
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(side_effect=Exception("connection error"))
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("api.routers.health.DB_DISPONIVEL", True), \
         patch("api.routers.health.SessionLocal", return_value=mock_session):
        r = client.get("/health")

    assert r.status_code == 200
    assert r.json()["banco_dados"] == "erro"


def test_max_tokens_fora_do_limite_retorna_422():
    """max_tokens=0 viola Query(ge=...) → 422 do FastAPI."""
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    OFX = b"OFXHEADER:100\n<OFX></OFX>"
    r = client.post("/conciliar/ofx?max_tokens=0",
                    files=[("arquivos", ("t.ofx", OFX, "application/x-ofx"))])
    assert r.status_code == 422
    assert "max_tokens" in str(r.json()["detail"])


def test_max_tokens_acima_do_limite_retorna_422():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    OFX = b"OFXHEADER:100\n<OFX></OFX>"
    r = client.post("/conciliar/ofx?max_tokens=99999",
                    files=[("arquivos", ("t.ofx", OFX, "application/x-ofx"))])
    assert r.status_code == 422
    assert "max_tokens" in str(r.json()["detail"])


# ── conciliacao.py — validacoes extras ────────────────────────────────────

def _client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


_OFX_MIN = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKACCTFROM><ACCTID>CCMIN</ACCTID></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260101</DTPOSTED>
<TRNAMT>1.00</TRNAMT><MEMO>Teste</MEMO></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""


def test_conciliar_ofx_cliente_id_invalido_retorna_422():
    c = _client()
    r = c.post("/conciliar/ofx?simular=true&cliente_id=nao-e-uuid",
               files=[("arquivos", ("t.ofx", _OFX_MIN, "application/x-ofx"))])
    assert r.status_code == 422
    assert "cliente_id" in str(r.json()["detail"]).lower()


def test_conciliar_ofx_muitos_arquivos_retorna_400():
    c = _client()
    files = [("arquivos", (f"f{i}.ofx", _OFX_MIN.encode(), "application/x-ofx")) for i in range(51)]
    r = c.post("/conciliar/ofx?simular=true", files=files)
    assert r.status_code == 400


def test_conciliar_csv_simular_retorna_200():
    c = _client()
    csv_data = "data,descricao,valor\n2026-01-01,Receita,100.00\n2026-01-02,Despesa,-50.00"
    r = c.post(
        "/conciliar/csv?simular=true",
        files=[
            ("extrato", ("extrato.csv", csv_data, "text/csv")),
            ("razao", ("razao.csv", csv_data, "text/csv")),
        ],
    )
    assert r.status_code == 200
    j = r.json()
    assert "relatorio_md" in j
    assert j["modo"] == "simulacao_local_csv"


def test_conciliar_csv_modelo_invalido_retorna_400():
    c = _client()
    csv_data = "data,descricao,valor\n2026-01-01,Receita,100.00"
    r = c.post(
        "/conciliar/csv?modelo=inexistente",
        files=[
            ("extrato", ("extrato.csv", csv_data, "text/csv")),
            ("razao", ("razao.csv", csv_data, "text/csv")),
        ],
    )
    assert r.status_code == 400


def test_conciliar_csv_cliente_id_invalido_retorna_422():
    c = _client()
    csv_data = "data,descricao,valor\n2026-01-01,Receita,100.00"
    r = c.post(
        "/conciliar/csv?simular=true&cliente_id=invalido",
        files=[
            ("extrato", ("extrato.csv", csv_data, "text/csv")),
            ("razao", ("razao.csv", csv_data, "text/csv")),
        ],
    )
    assert r.status_code == 422
    assert "cliente_id" in str(r.json()["detail"]).lower()


# ── conciliacoes_list.py ─────────────────────────────────────────────────

def test_conciliacoes_sem_db_retorna_503():
    c = _client()
    with patch("api.routers.conciliacoes_list.DB_DISPONIVEL", False):
        r = c.get("/conciliacoes")
    assert r.status_code == 503


def test_conciliacoes_cliente_id_invalido_retorna_400():
    c = _client()
    with patch("api.routers.conciliacoes_list.DB_DISPONIVEL", True):
        r = c.get("/conciliacoes?cliente_id=nao-e-uuid")
    assert r.status_code == 400


def test_conciliacoes_por_cliente_sem_db_retorna_503():
    c = _client()
    valid_uuid = "00000000-0000-0000-0000-000000000001"
    with patch("api.routers.conciliacoes_list.DB_DISPONIVEL", False):
        r = c.get(f"/conciliacoes/por-cliente/{valid_uuid}")
    assert r.status_code == 503


def test_conciliacoes_por_cliente_uuid_invalido_retorna_400():
    c = _client()
    with patch("api.routers.conciliacoes_list.DB_DISPONIVEL", True):
        r = c.get("/conciliacoes/por-cliente/nao-uuid")
    assert r.status_code == 400


def test_conciliacoes_buscar_sem_db_retorna_503():
    c = _client()
    with patch("api.routers.conciliacoes_list.DB_DISPONIVEL", False):
        r = c.get("/conciliacoes/algum-report-id")
    assert r.status_code == 503


# ── clientes.py — validacoes de UUID ──────────────────────────────────────

def test_cliente_buscar_uuid_invalido_retorna_400():
    c = _client()
    r = c.get("/clientes/nao-e-uuid")
    assert r.status_code == 400


def test_cliente_atualizar_uuid_invalido_retorna_400():
    c = _client()
    r = c.patch("/clientes/nao-e-uuid", json={"nome": "Novo Nome"})
    assert r.status_code == 400


# ── auth_routes.py — /auth/hash ───────────────────────────────────────────

def test_auth_hash_em_producao_retorna_404():
    c = _client()
    from api.services.auth import emitir_token
    token = emitir_token(sub="admin@x.com", email="admin@x.com", role="admin")
    with patch("api.core.config._IS_PROD", True):
        r = c.post("/auth/hash",
                   headers={"Authorization": f"Bearer {token}"},
                   json={"senha": "minha-senha-segura"})
    assert r.status_code == 404


def test_auth_hash_senha_curta_retorna_400():
    c = _client()
    from api.services.auth import emitir_token
    token = emitir_token(sub="admin@x.com", email="admin@x.com", role="admin")
    r = c.post("/auth/hash",
               headers={"Authorization": f"Bearer {token}"},
               json={"senha": "curta"})
    assert r.status_code == 400


def test_auth_hash_sucesso_retorna_hash():
    c = _client()
    from api.services.auth import emitir_token
    token = emitir_token(sub="admin@x.com", email="admin@x.com", role="admin")
    with patch.dict(os.environ, {"ORGCONC_ENV": "development"}):
        r = c.post("/auth/hash",
                   headers={"Authorization": f"Bearer {token}"},
                   json={"senha": "senha-forte-123"})
    assert r.status_code == 200
    assert "hash" in r.json()
    assert r.json()["hash"].startswith("$2b$")


# ── conciliacao.py — parse exception e empty result ───────────────────────

def test_conciliar_ofx_parse_exception_retorna_400():
    """Quando _parse_arquivo levanta excecao generica, deve retornar 400."""
    c = _client()
    with patch("api.routers.conciliacao._parse_arquivo", side_effect=ValueError("parse explodiu")):
        r = c.post("/conciliar/ofx?simular=true",
                   files=[("arquivos", ("t.ofx", _OFX_MIN, "application/x-ofx"))])
    assert r.status_code == 400


def test_conciliar_ofx_parse_retorna_vazio_retorna_400():
    """Quando _parse_arquivo retorna lista vazia, deve retornar 400."""
    c = _client()
    with patch("api.routers.conciliacao._parse_arquivo", return_value=[]):
        r = c.post("/conciliar/ofx?simular=true",
                   files=[("arquivos", ("t.ofx", _OFX_MIN, "application/x-ofx"))])
    assert r.status_code == 400
    assert "transacoes" in r.json()["detail"].lower()


def test_conciliar_ofx_llm_path_com_mock():
    """Testa o caminho LLM (sem simular) com mock do chamar_modelo_async."""
    c = _client()

    async def _mock_chamar(api_key, prompt, model_id, label, max_tokens):
        return {"texto": "# Relatorio LLM\n\nOk.", "input_tokens": 10, "output_tokens": 20,
                "erro": None, "modelo": model_id, "label": label}

    with patch("api.routers.conciliacao.chamar_modelo_async", side_effect=_mock_chamar), \
         patch("api.routers.conciliacao.get_api_key", return_value="sk-fake"):
        r = c.post("/conciliar/ofx?modelo=sonnet",
                   files=[("arquivos", ("t.ofx", _OFX_MIN, "application/x-ofx"))])
    assert r.status_code == 200
    j = r.json()
    assert j["modo"] == "claude_llm"
    assert "relatorio_md" in j


def test_conciliar_ofx_llm_retorna_erro_502():
    """Quando o LLM retorna erro, deve levantar 502."""
    c = _client()

    async def _mock_erro(api_key, prompt, model_id, label, max_tokens):
        return {"texto": "", "input_tokens": 0, "output_tokens": 0,
                "erro": "credit balance zero", "modelo": model_id, "label": label}

    with patch("api.routers.conciliacao.chamar_modelo_async", side_effect=_mock_erro), \
         patch("api.routers.conciliacao.get_api_key", return_value="sk-fake"):
        r = c.post("/conciliar/ofx?modelo=sonnet",
                   files=[("arquivos", ("t.ofx", _OFX_MIN, "application/x-ofx"))])
    assert r.status_code == 502


def test_conciliar_csv_llm_path_com_mock():
    """Testa caminho LLM do CSV com mock."""
    c = _client()
    csv_data = "data,descricao,valor\n2026-01-01,Receita,100.00"

    async def _mock_chamar(api_key, prompt, model_id, label, max_tokens):
        return {"texto": "# CSV Relatorio\n\nOk.", "input_tokens": 5, "output_tokens": 10,
                "erro": None, "modelo": model_id, "label": label}

    with patch("api.routers.conciliacao.chamar_modelo_async", side_effect=_mock_chamar), \
         patch("api.routers.conciliacao.get_api_key", return_value="sk-fake"):
        r = c.post("/conciliar/csv?modelo=sonnet",
                   files=[
                       ("extrato", ("e.csv", csv_data, "text/csv")),
                       ("razao", ("r.csv", csv_data, "text/csv")),
                   ])
    assert r.status_code == 200
    assert r.json()["modo"] == "claude_llm_csv"


# ── conciliacoes_list.py — serializar via mock ────────────────────────────

def test_conciliacoes_listar_com_mock_db():
    """Testa o caminho com DB disponivel retornando lista vazia."""
    c = _client()
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    class _FakeListarConcUC:
        def __init__(self, *a, **k):
            pass

        async def execute(self, _input):
            return []

    with patch("api.routers.conciliacoes_list.DB_DISPONIVEL", True), \
         patch("api.routers.conciliacoes_list.SessionLocal", return_value=mock_db), \
         patch("api.routers.conciliacoes_list.ListarConciliacoesUseCase", _FakeListarConcUC):
        r = c.get("/conciliacoes")
    assert r.status_code == 200
    assert r.json() == []
