"""Testes de api.services.storage.extrair_zip_seguro — proteção anti zip-bomb."""
from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import HTTPException

from api.core import config
from api.services import storage


def _zip(membros: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, data in membros.items():
            zf.writestr(nome, data)
    return buf.getvalue()


def test_extrai_apenas_membros_das_extensoes_pedidas():
    z = _zip({"nota1.xml": b"<nfe/>", "extrato.ofx": b"OFX", "leiame.txt": b"x"})
    out = storage.extrair_zip_seguro(z, (".xml", ".ofx"))
    assert {n for n, _ in out} == {"nota1.xml", "extrato.ofx"}  # .txt filtrado
    assert dict(out)["nota1.xml"] == b"<nfe/>"


def test_zip_invalido_retorna_400():
    with pytest.raises(HTTPException) as ei:
        storage.extrair_zip_seguro(b"isto-nao-e-um-zip", (".xml",))
    assert ei.value.status_code == 400


def test_excesso_de_membros_retorna_413(monkeypatch):
    monkeypatch.setattr(config, "ZIP_MAX_MEMBERS", 2)
    z = _zip({f"n{i}.xml": b"<a/>" for i in range(3)})
    with pytest.raises(HTTPException) as ei:
        storage.extrair_zip_seguro(z, (".xml",))
    assert ei.value.status_code == 413


def test_total_descomprimido_acima_do_teto_retorna_413(monkeypatch):
    monkeypatch.setattr(config, "ZIP_MAX_DECOMPRESSED_BYTES", 10)
    z = _zip({"grande.xml": b"x" * 1000})
    with pytest.raises(HTTPException) as ei:
        storage.extrair_zip_seguro(z, (".xml",))
    assert ei.value.status_code == 413


def test_razao_de_compressao_suspeita_retorna_413(monkeypatch):
    # 100k de zeros comprimem para ~poucas centenas de bytes -> razão altíssima.
    monkeypatch.setattr(config, "ZIP_MAX_RATIO", 2)
    monkeypatch.setattr(config, "ZIP_MAX_DECOMPRESSED_BYTES", 10 * 1024 * 1024)
    z = _zip({"bomba.xml": b"\x00" * 100_000})
    with pytest.raises(HTTPException) as ei:
        storage.extrair_zip_seguro(z, (".xml",))
    assert ei.value.status_code == 413


def test_zip_normal_dentro_dos_limites_nao_levanta():
    z = _zip({"a.xml": b"<a/>", "b.xml": b"<b/>"})
    out = storage.extrair_zip_seguro(z, (".xml",))
    assert len(out) == 2
