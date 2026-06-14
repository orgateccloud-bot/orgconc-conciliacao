"""Fila de jobs assíncronos (P1 #9): payload, handler do laudo e endpoints.

Roda SEM Postgres (CI): os endpoints que exigem DB devolvem 503; o núcleo de
geração (laudo_async) e o handler do worker são exercitados direto, com o OFX
sintético de tests/fixtures.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.auth import emitir_token
from api.services.job_queue import (
    HANDLERS,
    TIPO_LAUDO,
    desempacotar_uploads,
    empacotar_uploads,
)
from api.services.laudo_async import (
    FORMATOS_LAUDO,
    LaudoEntradaInvalida,
    gerar_laudo_documento,
)

FIXTURES = Path(__file__).parent / "fixtures"
OFX = (FIXTURES / "sample.ofx").read_bytes()

client = TestClient(app)


# ── Payload (ZIP em memória) ─────────────────────────────────────────────────


def test_empacotar_desempacotar_roundtrip():
    uploads = [
        ("extrato.ofx", OFX),
        ("notas.zip", b"PK\x05\x06" + b"\x00" * 18),
        ("nome com espaço.xml", b"<xml/>"),
    ]
    blob = empacotar_uploads(uploads)
    assert isinstance(blob, bytes) and blob
    assert desempacotar_uploads(blob) == uploads  # ordem e bytes preservados


def test_empacotar_lista_vazia():
    assert desempacotar_uploads(empacotar_uploads([])) == []


# ── Núcleo compartilhado (laudo_async) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_gerar_laudo_documento_xlsx():
    conteudo, nome, mime = await gerar_laudo_documento(
        [("extrato.ofx", OFX)], empresa_cnpj="11222333000181", conta="", formato="xlsx")
    assert conteudo[:2] == b"PK"  # XLSX é um ZIP
    assert nome.startswith("laudo_") and nome.endswith(".xlsx")
    assert "spreadsheetml" in mime


@pytest.mark.asyncio
async def test_gerar_laudo_documento_html():
    conteudo, nome, mime = await gerar_laudo_documento(
        [("extrato.ofx", OFX)], empresa_cnpj="11222333000181", conta="", formato="html")
    assert b"<html" in conteudo.lower()
    assert nome.endswith(".html") and mime.startswith("text/html")


@pytest.mark.asyncio
async def test_gerar_laudo_documento_entradas_invalidas():
    with pytest.raises(LaudoEntradaInvalida):
        await gerar_laudo_documento([("x.ofx", OFX)], "11222333000181", "", "doc")
    with pytest.raises(LaudoEntradaInvalida):
        await gerar_laudo_documento([], "11222333000181", "", "xlsx")
    with pytest.raises(LaudoEntradaInvalida):  # sem OFX válido
        await gerar_laudo_documento([("nota.xml", b"<x/>")], "11222333000181", "", "xlsx")
    with pytest.raises(LaudoEntradaInvalida):  # conta sem transações
        await gerar_laudo_documento([("x.ofx", OFX)], "11222333000181", "999999", "xlsx")


# ── Handler do worker (mesmo documento do endpoint síncrono) ─────────────────


@pytest.mark.asyncio
async def test_handler_laudo_do_worker():
    handler = HANDLERS[TIPO_LAUDO]
    blob = empacotar_uploads([("extrato.ofx", OFX)])
    conteudo, nome, mime = await handler(
        {"empresa_cnpj": "11222333000181", "conta": "", "formato": "xlsx"}, blob)
    assert conteudo[:2] == b"PK"
    assert nome.endswith(".xlsx") and "spreadsheetml" in mime


@pytest.mark.asyncio
async def test_handler_laudo_sem_arquivos_falha():
    with pytest.raises(ValueError):
        await HANDLERS[TIPO_LAUDO]({"formato": "xlsx"}, None)


# ── Endpoints: sem DB a fila responde 503 (e nunca 500) ──────────────────────


def test_laudo_async_sem_db_responde_503():
    r = client.post(
        "/fiscal/laudo/async",
        data={"empresa_cnpj": "11222333000181"},
        files=[("arquivos", ("extrato.ofx", OFX, "application/octet-stream"))],
    )
    assert r.status_code == 503
    assert "banco" in r.json()["detail"].lower()


def test_jobs_endpoints_sem_db_respondem_503():
    assert client.get("/jobs").status_code == 503
    assert client.get("/jobs/00000000-0000-0000-0000-000000000000").status_code == 503
    assert client.get("/v1/jobs").status_code == 503  # dual-mount /v1


def test_formatos_laudo_expostos():
    assert FORMATOS_LAUDO == {"xlsx", "html", "pdf"}


# ── #29 / #37: validação de CNPJ e hard-limit de jobs por org ────────────────


def _token_org() -> str:
    """Token com org_id (necessário p/ enfileirar laudo async)."""
    return emitir_token(
        sub=f"w7-{uuid.uuid4()}@x.com",
        email="w7@x.com",
        org_id=str(uuid.uuid4()),
        role="admin",
    )


def test_laudo_async_cnpj_invalido_400():
    """#29: empresa_cnpj sem 14 dígitos -> 400 (antes de enfileirar)."""
    with (
        patch("api.routers.fiscal.DB_DISPONIVEL", True),
        patch("api.routers.fiscal.SessionLocal", MagicMock()),
    ):
        r = client.post(
            "/fiscal/laudo/async",
            data={"empresa_cnpj": "123"},
            files=[("arquivos", ("extrato.ofx", OFX, "application/octet-stream"))],
            headers={"Authorization": f"Bearer {_token_org()}"},
        )
    assert r.status_code == 400
    assert "14" in r.json()["detail"]


def test_laudo_async_excede_teto_jobs_429():
    """#37: org com >= MAX jobs em aberto -> 429 (não enfileira)."""
    from api.routers.fiscal import MAX_JOBS_LAUDO_POR_ORG

    # Sessão mockada: a contagem de jobs em aberto devolve o teto.
    db = AsyncMock()
    db.add = MagicMock()
    res = MagicMock()
    res.scalar = MagicMock(return_value=MAX_JOBS_LAUDO_POR_ORG)
    db.execute = AsyncMock(return_value=res)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    session_local = MagicMock(return_value=cm)

    with (
        patch("api.routers.fiscal.DB_DISPONIVEL", True),
        patch("api.routers.fiscal.SessionLocal", session_local),
    ):
        r = client.post(
            "/fiscal/laudo/async",
            data={"empresa_cnpj": "11222333000181"},
            files=[("arquivos", ("extrato.ofx", OFX, "application/octet-stream"))],
            headers={"Authorization": f"Bearer {_token_org()}"},
        )
    assert r.status_code == 429
    assert "jobs em aberto" in r.json()["detail"].lower()
    db.add.assert_not_called()  # não enfileirou
