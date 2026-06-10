"""Fila de jobs assíncronos em Postgres (P1 #9) — tarefas fiscais longas.

Sem infra nova: a fila é a tabela `jobs` (migration 023) e o worker é um loop
asyncio iniciado no lifespan de CADA réplica web (api/core/bootstrap.py). O
claim usa `FOR UPDATE SKIP LOCKED`, então N réplicas competem sem duplicar
trabalho; se um dia houver serviço worker dedicado no Railway, o mesmo loop
roda lá (e desliga-se nas réplicas web com ORGCONC_JOBS_WORKER=0).

RLS: o loop roda com o contexto worker (GUC app.worker → policy worker_access)
apenas nas operações DE FILA (claim/finalizar/limpeza). A EXECUÇÃO do handler
roda com `set_org_context(org_id do job)` — todo acesso a dados do tenant fica
escopado pela org_isolation normal.

Ciclo de vida: PENDENTE → EXECUTANDO → CONCLUIDO | ERRO. Jobs EXECUTANDO além
de ORGCONC_JOBS_TIMEOUT_MIN são re-enfileirados (réplica morreu) até
ORGCONC_JOBS_MAX_TENTATIVAS; depois viram ERRO. Concluídos/errados são
removidos após ORGCONC_JOBS_TTL_H (resultado em BYTEA não acumula no banco).
"""
from __future__ import annotations

import asyncio
import io
import logging
import zipfile

from sqlalchemy import text

from api.core import config as _config
from api.db.rls_context import (
    reset_org_context,
    reset_worker_context,
    set_org_context,
    set_worker_context,
)

log = logging.getLogger("orgconc.jobs")

STATUS_PENDENTE = "PENDENTE"
STATUS_EXECUTANDO = "EXECUTANDO"
STATUS_CONCLUIDO = "CONCLUIDO"
STATUS_ERRO = "ERRO"

TIPO_LAUDO = "laudo_forense"


# ── Payload de uploads: lista (nome, bytes) <-> ZIP em memória ───────────────


def empacotar_uploads(uploads: list[tuple[str, bytes]]) -> bytes:
    """Serializa uploads num ZIP (deflate) p/ guardar em jobs.arquivos (BYTEA)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, (nome, conteudo) in enumerate(uploads):
            # Prefixo de índice preserva ordem e evita colisão de nomes.
            zf.writestr(f"{i:04d}__{nome}", conteudo)
    return buf.getvalue()


def desempacotar_uploads(blob: bytes) -> list[tuple[str, bytes]]:
    """Inverso de empacotar_uploads — restaura [(nome, bytes)] na ordem."""
    uploads: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for member in sorted(zf.namelist()):
            nome = member.split("__", 1)[1] if "__" in member else member
            uploads.append((nome, zf.read(member)))
    return uploads


# ── Handlers por tipo de job ─────────────────────────────────────────────────


async def _executar_laudo(params: dict, arquivos: bytes | None) -> tuple[bytes, str, str]:
    from api.services.laudo_async import gerar_laudo_documento

    if not arquivos:
        raise ValueError("Job de laudo sem arquivos.")
    uploads = desempacotar_uploads(arquivos)
    return await gerar_laudo_documento(
        uploads,
        empresa_cnpj=params.get("empresa_cnpj", ""),
        conta=params.get("conta", ""),
        formato=params.get("formato", "xlsx"),
    )


HANDLERS = {
    TIPO_LAUDO: _executar_laudo,
}


# ── Operações de fila (rodam com o contexto worker) ──────────────────────────


async def _claim_proximo_job():
    """Claima 1 job PENDENTE (mais antigo) — atômico via SKIP LOCKED.

    Devolve (id, tipo, params, arquivos, org_id) ou None. Os blobs vêm juntos
    para a execução não precisar de novo SELECT cross-org.
    """
    from api.core.config import SessionLocal

    tk = set_worker_context(True)
    try:
        async with SessionLocal() as db:
            row = (await db.execute(text(
                """
                UPDATE jobs SET status = :exec, iniciado_em = now(),
                       tentativas = tentativas + 1
                WHERE id = (
                    SELECT id FROM jobs WHERE status = :pend
                    ORDER BY criado_em LIMIT 1 FOR UPDATE SKIP LOCKED
                )
                RETURNING id, tipo, params, arquivos, org_id
                """), {"exec": STATUS_EXECUTANDO, "pend": STATUS_PENDENTE},
            )).first()
            await db.commit()
            return row
    finally:
        reset_worker_context(tk)


async def _finalizar_job(job_id, *, resultado=None, nome=None, mime=None, erro=None) -> None:
    from api.core.config import SessionLocal

    tk = set_worker_context(True)
    try:
        async with SessionLocal() as db:
            if erro is None:
                await db.execute(text(
                    """
                    UPDATE jobs SET status = :st, resultado = :res,
                           resultado_nome = :nome, resultado_mime = :mime,
                           arquivos = NULL, erro = NULL, concluido_em = now()
                    WHERE id = :id
                    """), {"st": STATUS_CONCLUIDO, "res": resultado,
                           "nome": nome, "mime": mime, "id": job_id})
            else:
                await db.execute(text(
                    """
                    UPDATE jobs SET status = :st, erro = :erro,
                           arquivos = NULL, concluido_em = now()
                    WHERE id = :id
                    """), {"st": STATUS_ERRO, "erro": erro[:2000], "id": job_id})
            await db.commit()
    finally:
        reset_worker_context(tk)


async def _manutencao_fila() -> None:
    """Re-enfileira jobs órfãos (réplica morreu no meio) e remove expirados."""
    from api.core.config import SessionLocal

    tk = set_worker_context(True)
    try:
        async with SessionLocal() as db:
            # Órfãos com tentativas restantes voltam p/ fila; sem restantes → ERRO.
            await db.execute(text(
                """
                UPDATE jobs SET status = :pend, iniciado_em = NULL
                WHERE status = :exec
                  AND iniciado_em < now() - make_interval(mins => :tmin)
                  AND tentativas < :maxt
                """), {"pend": STATUS_PENDENTE, "exec": STATUS_EXECUTANDO,
                       "tmin": _config.JOBS_TIMEOUT_MIN,
                       "maxt": _config.JOBS_MAX_TENTATIVAS})
            await db.execute(text(
                """
                UPDATE jobs SET status = :err, arquivos = NULL,
                       erro = 'timeout: excedeu as tentativas', concluido_em = now()
                WHERE status = :exec
                  AND iniciado_em < now() - make_interval(mins => :tmin)
                """), {"err": STATUS_ERRO, "exec": STATUS_EXECUTANDO,
                       "tmin": _config.JOBS_TIMEOUT_MIN})
            # TTL: concluídos/errados antigos saem do banco (BYTEA não acumula).
            await db.execute(text(
                """
                DELETE FROM jobs
                WHERE status IN (:ok, :err)
                  AND concluido_em < now() - make_interval(hours => :ttl)
                """), {"ok": STATUS_CONCLUIDO, "err": STATUS_ERRO,
                       "ttl": _config.JOBS_TTL_HORAS})
            await db.commit()
    finally:
        reset_worker_context(tk)


# ── Execução de 1 job + loop ─────────────────────────────────────────────────


async def processar_um_job() -> bool:
    """Claima e executa 1 job. Devolve False se a fila estava vazia."""
    row = await _claim_proximo_job()
    if row is None:
        return False
    job_id, tipo, params, arquivos, org_id = row
    log.info("job %s claimado (tipo=%s org=%s)", job_id, tipo, org_id)

    # Handler roda com o contexto da ORG DO JOB — acesso a dados do tenant
    # (ex.: cache de CNPJ em DB) fica sob a org_isolation normal.
    org_tk = set_org_context(str(org_id)) if org_id else None
    try:
        handler = HANDLERS.get(tipo)
        if handler is None:
            raise ValueError(f"tipo de job desconhecido: {tipo}")
        conteudo, nome, mime = await handler(params or {}, arquivos)
        await _finalizar_job(job_id, resultado=conteudo, nome=nome, mime=mime)
        log.info("job %s concluido (%s, %d bytes)", job_id, nome, len(conteudo))
    except Exception as e:  # noqa: BLE001 — erro do job não derruba o worker
        log.warning("job %s falhou: %s", job_id, e)
        await _finalizar_job(job_id, erro=str(e))
    finally:
        if org_tk is not None:
            reset_org_context(org_tk)
    return True


async def worker_loop() -> None:
    """Loop do worker — iniciado no lifespan quando há DB e a flag está ligada.

    Resiliente: erro inesperado (DB fora etc.) é logado e o loop continua após
    o intervalo de polling. Cancelamento (shutdown) propaga.
    """
    log.info("worker de jobs iniciado (poll=%ss timeout=%smin ttl=%sh)",
             _config.JOBS_POLL_S, _config.JOBS_TIMEOUT_MIN, _config.JOBS_TTL_HORAS)
    ciclo = 0
    while True:
        try:
            # Manutenção (órfãos/TTL) a cada ~20 ciclos — barata, mas sem rodar
            # a cada poll.
            if ciclo % 20 == 0:
                await _manutencao_fila()
            ciclo += 1
            if not await processar_um_job():
                await asyncio.sleep(_config.JOBS_POLL_S)
        except asyncio.CancelledError:
            log.info("worker de jobs encerrando (shutdown)")
            raise
        except Exception:  # noqa: BLE001
            log.exception("worker de jobs: erro no ciclo — segue após poll")
            await asyncio.sleep(_config.JOBS_POLL_S)
