from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from api.core.config import DB_DISPONIVEL, SessionLocal, crud_clientes
from api.core.rate_limit import limiter
from api.schemas import ClienteCreate, ClienteUpdate
from api.services.audit import gravar_audit_independente
from api.services.auth import TokenPayload, current_user

router = APIRouter(prefix="/clientes", tags=["clientes"], dependencies=[Depends(current_user)])


@router.post("", status_code=201)
@limiter.limit("20/minute")
async def criar_cliente(
    request: Request,
    payload: ClienteCreate,
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    try:
        async with SessionLocal() as db:
            cliente = await crud_clientes.criar_cliente(
                db,
                nome=payload.nome,
                cnpj=payload.cnpj,
                email=payload.email,
                telefone=payload.telefone,
                plano=payload.plano,
            )
    except IntegrityError:
        raise HTTPException(409, "CNPJ ja cadastrado")
    await gravar_audit_independente(
        action="cliente.criar",
        resource_type="cliente",
        resource_id=str(cliente.id),
        payload={"nome": cliente.nome, "plano": cliente.plano},
        actor=user,
    )
    return {
        "id": str(cliente.id),
        "nome": cliente.nome,
        "cnpj": cliente.cnpj,
        "email": cliente.email,
        "plano": cliente.plano,
        "ativo": cliente.ativo,
        "criado_em": cliente.criado_em.isoformat(),
    }


@router.get("")
@limiter.limit("30/minute")
async def listar_clientes(request: Request, apenas_ativos: bool = True):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as db:
        clientes = await crud_clientes.listar_clientes(db, apenas_ativos=apenas_ativos)
    return [
        {"id": str(c.id), "nome": c.nome, "cnpj": c.cnpj, "email": c.email, "plano": c.plano, "ativo": c.ativo}
        for c in clientes
    ]


@router.get("/{cliente_id}")
@limiter.limit("30/minute")
async def buscar_cliente(request: Request, cliente_id: str):
    # fix(#6): validar UUID antes de checar DB_DISPONIVEL para retornar 400
    # corretamente para IDs invalidos independente do estado do banco.
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "ID invalido")
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as db:
        cliente = await crud_clientes.buscar_cliente(db, cid)
    if not cliente:
        raise HTTPException(404, "Cliente nao encontrado")
    return {
        "id": str(cliente.id),
        "nome": cliente.nome,
        "cnpj": cliente.cnpj,
        "email": cliente.email,
        "telefone": cliente.telefone,
        "plano": cliente.plano,
        "ativo": cliente.ativo,
        "criado_em": cliente.criado_em.isoformat(),
    }


@router.patch("/{cliente_id}")
@limiter.limit("20/minute")
async def atualizar_cliente(
    request: Request,
    cliente_id: str,
    payload: ClienteUpdate,
    user: TokenPayload = Depends(current_user),
):
    # fix(#6): validar UUID antes de checar DB_DISPONIVEL para retornar 400
    # corretamente para IDs invalidos independente do estado do banco.
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "ID invalido")
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    campos = {k: v for k, v in payload.model_dump().items() if v is not None}
    async with SessionLocal() as db:
        cliente = await crud_clientes.atualizar_cliente(db, cid, **campos)
    if not cliente:
        raise HTTPException(404, "Cliente nao encontrado")
    await gravar_audit_independente(
        action="cliente.atualizar",
        resource_type="cliente",
        resource_id=str(cliente.id),
        payload={"campos_alterados": list(campos.keys())},
        actor=user,
    )
    return {"id": str(cliente.id), "nome": cliente.nome, "plano": cliente.plano, "ativo": cliente.ativo}
