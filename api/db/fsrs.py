"""CRUD para fsrs_memorias — revisão espaçada de padrões contábeis."""
import uuid
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import FsrsMemoria


def _fsrs_proximo_intervalo(
    estabilidade: float,
    dificuldade: float,
    grade: int,
) -> tuple[float, float, date]:
    """Calcula próximo intervalo usando algoritmo FSRS simplificado.

    grade: 0=esqueceu, 1=difícil, 2=bom, 3=fácil
    Retorna (nova_estabilidade, nova_dificuldade, proxima_revisao)
    """
    if grade == 0:
        nova_est = max(1.0, estabilidade * 0.2)
        nova_dif = min(1.0, dificuldade + 0.2)
        intervalo = 1
    elif grade == 1:
        nova_est = estabilidade * 1.2
        nova_dif = min(1.0, dificuldade + 0.1)
        intervalo = max(1, int(estabilidade * 0.8))
    elif grade == 2:
        fator = 1.0 + max(0.1, 0.9 - dificuldade)
        nova_est = estabilidade * fator
        nova_dif = max(0.1, dificuldade - 0.05)
        intervalo = max(1, int(nova_est))
    else:  # grade == 3: fácil
        fator = 1.0 + max(0.1, 1.2 - dificuldade)
        nova_est = estabilidade * fator
        nova_dif = max(0.1, dificuldade - 0.1)
        intervalo = max(1, int(nova_est * 1.3))

    proxima = date.today() + timedelta(days=intervalo)
    return round(nova_est, 4), round(nova_dif, 4), proxima


async def listar_pendentes(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    limite: int = 20,
) -> list[FsrsMemoria]:
    """Retorna padrões com revisão vencida ou vencendo hoje."""
    q = (
        select(FsrsMemoria)
        .where(FsrsMemoria.cliente_id == cliente_id)
        .where(FsrsMemoria.proxima_revisao <= date.today())
        .order_by(FsrsMemoria.proxima_revisao)
        .limit(limite)
    )
    res = await db.execute(q)
    return list(res.scalars().all())


async def listar_todos(
    db: AsyncSession,
    cliente_id: uuid.UUID,
) -> list[FsrsMemoria]:
    q = (
        select(FsrsMemoria)
        .where(FsrsMemoria.cliente_id == cliente_id)
        .order_by(FsrsMemoria.proxima_revisao)
    )
    res = await db.execute(q)
    return list(res.scalars().all())


async def buscar_por_pattern(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    pattern_key: str,
) -> FsrsMemoria | None:
    q = select(FsrsMemoria).where(
        FsrsMemoria.cliente_id == cliente_id,
        FsrsMemoria.pattern_key == pattern_key,
    )
    res = await db.execute(q)
    return res.scalar_one_or_none()


async def registrar_ou_atualizar(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    pattern_key: str,
    categoria: str,
    pattern_exemplo: str | None = None,
) -> FsrsMemoria:
    """Cria memória se não existe; atualiza categoria se já existe."""
    mem = await buscar_por_pattern(db, cliente_id, pattern_key)
    if mem is None:
        mem = FsrsMemoria(
            cliente_id=cliente_id,
            pattern_key=pattern_key,
            pattern_exemplo=pattern_exemplo,
            categoria=categoria,
        )
        db.add(mem)
    else:
        mem.categoria = categoria
        if pattern_exemplo:
            mem.pattern_exemplo = pattern_exemplo
    await db.commit()
    await db.refresh(mem)
    return mem


async def registrar_revisao(
    db: AsyncSession,
    cliente_id: uuid.UUID,
    pattern_key: str,
    grade: int,
) -> FsrsMemoria | None:
    """Aplica FSRS após revisão e atualiza agenda."""
    if grade not in (0, 1, 2, 3):
        return None
    mem = await buscar_por_pattern(db, cliente_id, pattern_key)
    if mem is None:
        return None
    nova_est, nova_dif, proxima = _fsrs_proximo_intervalo(
        mem.estabilidade, mem.dificuldade, grade
    )
    mem.estabilidade = nova_est
    mem.dificuldade = nova_dif
    mem.proxima_revisao = proxima
    mem.repeticoes += 1
    if grade == 0:
        mem.lapsos += 1
    await db.commit()
    await db.refresh(mem)
    return mem
