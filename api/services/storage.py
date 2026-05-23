"""Persistencia JSON em disco (rolling window de 50 arquivos)."""
from __future__ import annotations

import json
import re
import uuid

from fastapi import HTTPException, UploadFile

from api.core.config import DATA_DIR, log


async def read_limited(up: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await up.read(1024 * 256)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Arquivo {up.filename} excede limite de upload",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def salvar_dataset(
    extratos: list[dict],
    anomalias: list[dict],
    relatorio: str,
    owner_sub: str | None = None,
) -> str:
    rid = uuid.uuid4().hex[:12]
    path = DATA_DIR / f"{rid}.json"
    payload = {
        "extratos": extratos,
        "anomalias": anomalias,
        "relatorio": relatorio,
        "owner_sub": owner_sub,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    existing = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in existing[50:]:
        try:
            old.unlink()
        except OSError:
            pass
    log.info("Dataset salvo: %s (owner=%s)", rid, owner_sub or "anonymous")
    return rid


def carregar_dataset(rid: str, verify_sub: str | None = None) -> dict:
    if not re.fullmatch(r"[a-f0-9]{12}", rid):
        raise HTTPException(status_code=400, detail="ID invalido")
    path = DATA_DIR / f"{rid}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado ou expirado")
    data = json.loads(path.read_text(encoding="utf-8"))
    if verify_sub and data.get("owner_sub") != verify_sub:
        raise HTTPException(status_code=403, detail="Acesso negado a este relatorio")
    return data
