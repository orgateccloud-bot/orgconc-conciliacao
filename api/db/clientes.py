"""CRUD de clientes."""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Cliente


async def criar_cliente(db: AsyncSession, nome: str, cnpj: str | None = None,
                        email: str | None = None, telefone: str | None = None,
                        plano: str = "basico") -> Cliente:
    cliente = Cliente(nome=nome, cnpj=cnpj, email=email, telefone=telefone, plano=plano)
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return cliente


async def buscar_cliente(db: AsyncSession, cliente_id: uuid.UUID) -> Cliente | None:
    return await db.get(Cliente, cliente_id)


async def buscar_por_cnpj(db: AsyncSession, cnpj: str) -> Cliente | None:
    resultado = await db.execute(select(Cliente).where(Cliente.cnpj == cnpj))
    return resultado.scalar_one_or_none()


async def listar_clientes(db: AsyncSession, apenas_ativos: bool = True) -> list[Cliente]:
    query = select(Cliente)
    if apenas_ativos:
        query = query.where(Cliente.ativo == True)
    resultado = await db.execute(query.order_by(Cliente.nome))
    return list(resultado.scalars().all())


async def atualizar_cliente(db: AsyncSession, cliente_id: uuid.UUID,
                            **campos) -> Cliente | None:
    cliente = await buscar_cliente(db, cliente_id)
    if not cliente:
        return None
    for campo, valor in campos.items():
        if hasattr(cliente, campo):
            setattr(cliente, campo, valor)
    await db.commit()
    await db.refresh(cliente)
    return cliente
