"""Tasks Arq — funcoes async registradas no worker.

Cada task recebe `ctx` (contexto Arq) + args. Para acessar DB, abre sua
propria session — o pool foi configurado para o web process; aqui rodamos
em processo separado.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from api.core.config import SessionLocal
from api.db import jobs as jobs_repo

log = logging.getLogger("orgconc.tasks")


async def ping_task(ctx: dict, mensagem: str = "pong") -> dict:
    """Task trivial para validar que o worker esta vivo."""
    log.info("ping_task: %s", mensagem)
    return {"resposta": mensagem, "ctx_keys": list(ctx.keys())}


async def conciliar_ofx_task(ctx: dict, job_id: str) -> dict:
    """Processa uma conciliacao OFX assincronamente.

    Hoje a logica completa (parse + LLM + persist) ainda mora no router
    de `conciliacao.py`. Esta task eh um esqueleto pronto para receber a
    extracao do use case `ConciliarOFXUseCase` (item 8, pendente p/ esse
    fluxo especifico).
    """
    if SessionLocal is None:
        raise RuntimeError("DB nao configurado — worker precisa do DB para gravar Job")

    jid = uuid.UUID(job_id)
    async with SessionLocal() as db:
        await jobs_repo.marcar_running(db, jid)
        job = await jobs_repo.buscar(db, jid)
        if job is None or job.input_json is None:
            raise RuntimeError(f"Job {jid} sem input")
        _input: dict[str, Any] = json.loads(job.input_json)

    try:
        # TODO: substituir por ConciliarOFXUseCase.execute(_input)
        # Por ora, ack sintetico para validar o pipeline end-to-end.
        await _atualizar_progresso(jid, 50)
        await _atualizar_progresso(jid, 100)
        output = {
            "modo": _input.get("modo", "desconhecido"),
            "report_id": f"pending-{jid.hex[:8]}",
            "mensagem": "Worker rodou ok — logica de conciliacao sera plugada no proximo PR",
        }

        async with SessionLocal() as db:
            await jobs_repo.marcar_done(db, jid, output)
        return output
    except Exception as exc:
        log.exception("conciliar_ofx_task falhou %s", jid)
        async with SessionLocal() as db:
            await jobs_repo.marcar_failed(db, jid, f"{type(exc).__name__}: {exc}")
        raise


async def _atualizar_progresso(job_id: uuid.UUID, pct: int) -> None:
    if SessionLocal is None:
        return
    async with SessionLocal() as db:
        await jobs_repo.atualizar_progresso(db, job_id, pct)
