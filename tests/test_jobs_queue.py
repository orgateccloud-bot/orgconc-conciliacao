"""Fila de jobs assíncronos (P1 #9): payload, handler do laudo e endpoints.

Roda SEM Postgres (CI): os endpoints que exigem DB devolvem 503; o núcleo de
geração (laudo_async) e o handler do worker são exercitados direto, com o OFX
sintético de tests/fixtures.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
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
