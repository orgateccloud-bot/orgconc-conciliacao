"""Arq WorkerSettings — registra as funcoes que podem ser enfileiradas."""
from __future__ import annotations

import logging

from arq.connections import RedisSettings

from api.infra.queue.arq_pool import _settings
from api.workers.tasks import conciliar_ofx_task, ping_task

log = logging.getLogger("orgconc.worker")


async def startup(ctx) -> None:
    log.info("Worker iniciando")


async def shutdown(ctx) -> None:
    log.info("Worker encerrando")


class WorkerSettings:
    """Importado pelo CLI Arq: `arq api.workers.WorkerSettings`."""
    redis_settings: RedisSettings = _settings()
    functions = [conciliar_ofx_task, ping_task]
    max_jobs = 4
    job_timeout = 300  # 5 min — LLM long
    on_startup = startup
    on_shutdown = shutdown
