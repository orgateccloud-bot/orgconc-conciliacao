"""Singleton de pool Arq (cliente do worker)."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

log = logging.getLogger("orgconc.queue")

_pool: ArqRedis | None = None


def _settings() -> RedisSettings:
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    return RedisSettings.from_dsn(url)


async def get_arq_pool() -> ArqRedis:
    """Singleton — abre conexao na primeira chamada."""
    global _pool
    if _pool is None:
        _pool = await create_pool(_settings())
        log.info("Arq pool inicializado")
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close(close_connection_pool=True)
        _pool = None


async def enqueue_job(
    funcao: str,
    *args: Any,
    job_id: uuid.UUID | None = None,
    **kwargs: Any,
) -> str:
    """Enfileira `funcao` (nome registrado no WorkerSettings).

    Retorna o id Arq (usado por jobs internos do Arq; o ID 'de negocio' eh
    o UUID que persistimos na tabela `jobs`).
    """
    pool = await get_arq_pool()
    _job_id_str = str(job_id) if job_id else None
    job = await pool.enqueue_job(funcao, *args, _job_id=_job_id_str, **kwargs)
    if job is None:
        raise RuntimeError(f"Falha ao enfileirar {funcao} (job ja existe?)")
    return job.job_id
