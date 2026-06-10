"""Persistencia de datasets de conciliacao.

Preferencia: Postgres (tabela reconciliacao_datasets) quando o DB esta
disponivel — datasets compartilhados entre replicas, habilitando escala
horizontal. Fallback: disco local (DATA_DIR/{rid}.json, janela rolante de 50)
quando nao ha DB — preserva o modo "DB opcional" usado em dev/CI.

As funcoes seguem sincronas (psycopg2) para nao propagar async aos call-sites.
O custo de uma query de 1 linha e desprezivel perto do parsing/LLM dos endpoints.
"""
from __future__ import annotations

import io
import json
import re
import uuid
import zipfile

from fastapi import HTTPException, UploadFile

from api.core import config
from api.core.config import DATA_DIR, log

_RID_RX = re.compile(r"[a-f0-9]{12}")


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


def extrair_zip_seguro(conteudo: bytes, exts: tuple[str, ...]) -> list[tuple[str, bytes]]:
    """Extrai membros de um ZIP cujo nome termina em ``exts``, com proteção anti
    zip-bomb: limita número de membros, total descomprimido e razão de compressão
    (descomprimido/comprimido). O limite de upload cobre só o tamanho comprimido;
    este cobre a inflação em memória.

    Levanta HTTPException(400) para ZIP inválido e 413 ao estourar um limite.
    """
    comprimido = max(1, len(conteudo))
    selecionados: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            if len(infos) > config.ZIP_MAX_MEMBERS:
                raise HTTPException(
                    status_code=413,
                    detail=f"ZIP com {len(infos)} arquivos excede o limite de {config.ZIP_MAX_MEMBERS}.",
                )
            total_declarado = sum(i.file_size for i in infos)
            if total_declarado > config.ZIP_MAX_DECOMPRESSED_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"ZIP descomprime para ~{total_declarado // (1024 * 1024)} MB "
                        f"(limite {config.ZIP_MAX_DECOMPRESSED_MB} MB)."
                    ),
                )
            if total_declarado / comprimido > config.ZIP_MAX_RATIO:
                raise HTTPException(
                    status_code=413,
                    detail="Razão de compressão do ZIP suspeita (possível zip bomb).",
                )
            lido = 0
            for info in infos:
                if not info.filename.lower().endswith(exts):
                    continue
                lido += info.file_size
                if lido > config.ZIP_MAX_DECOMPRESSED_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Total descomprimido do ZIP excede o limite.",
                    )
                with zf.open(info) as fh:
                    selecionados.append((info.filename, fh.read()))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Arquivo não é um ZIP válido.")
    return selecionados


def _db_url() -> str:
    return (config._DB_URL or "").strip().replace("postgresql+asyncpg://", "postgresql://", 1)


def _salvar_db(rid: str, owner_sub: str | None, payload: dict) -> bool:
    """Grava o dataset no Postgres. True se gravou; False se indisponivel/erro."""
    url = _db_url()
    if not url:
        return False
    try:
        import psycopg2
        from psycopg2.extras import Json

        conn = psycopg2.connect(url, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO reconciliacao_datasets (id, owner_sub, payload) "
                    "VALUES (%s, %s, %s)",
                    (rid, owner_sub, Json(payload)),
                )
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception:
        log.warning("Falha ao gravar dataset no DB; fallback para arquivo", exc_info=True)
        return False


def _carregar_db(rid: str) -> dict | None:
    """Le o dataset do Postgres. dict (payload) ou None se ausente/indisponivel."""
    url = _db_url()
    if not url:
        return None
    try:
        import psycopg2

        conn = psycopg2.connect(url, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM reconciliacao_datasets WHERE id = %s", (rid,)
                )
                row = cur.fetchone()
        finally:
            conn.close()
        return dict(row[0]) if row else None
    except Exception:
        log.warning("Falha ao ler dataset do DB; tentando arquivo", exc_info=True)
        return None


def salvar_dataset(
    extratos: list[dict],
    anomalias: list[dict],
    relatorio: str,
    owner_sub: str | None = None,
) -> str:
    rid = uuid.uuid4().hex[:12]
    payload = {
        "extratos": extratos,
        "anomalias": anomalias,
        "relatorio": relatorio,
        "owner_sub": owner_sub,
    }
    if config.DB_DISPONIVEL and _salvar_db(rid, owner_sub, payload):
        log.info("Dataset salvo no DB: %s (owner=%s)", rid, owner_sub or "anonymous")
        return rid

    # Fallback: arquivo local (janela rolante de 50)
    path = DATA_DIR / f"{rid}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    existing = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in existing[50:]:
        try:
            old.unlink()
        except OSError:
            pass
    log.info("Dataset salvo em arquivo: %s (owner=%s)", rid, owner_sub or "anonymous")
    return rid


def carregar_dataset(rid: str, verify_sub: str | None = None) -> dict:
    if not _RID_RX.fullmatch(rid):
        raise HTTPException(status_code=400, detail="ID invalido")

    data = _carregar_db(rid) if config.DB_DISPONIVEL else None
    if data is None:
        path = DATA_DIR / f"{rid}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Relatorio nao encontrado ou expirado")
        data = json.loads(path.read_text(encoding="utf-8"))

    if verify_sub and data.get("owner_sub") != verify_sub:
        raise HTTPException(status_code=403, detail="Acesso negado a este relatorio")
    return data
