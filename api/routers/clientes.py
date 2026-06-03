from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from api.core.config import DB_DISPONIVEL, SessionLocal, crud_clientes
from api.core.rate_limit import limiter
from api.domain.exceptions import RegraViolada, ValorInvalido
from api.infra.repositories.clientes import ClienteRepositorySQL
from api.schemas import ClienteCreate, ClienteUpdate
from api.services.audit import gravar_audit_independente
from api.services.auth import TokenPayload, autorizar_cliente, current_user
from api.usecases.criar_cliente import CriarClienteInput, CriarClienteUseCase
from api.usecases.listar_clientes import ListarClientesInput, ListarClientesUseCase

router = APIRouter(prefix="/clientes", tags=["clientes"], dependencies=[Depends(current_user)])

# Arquitetura limpa (fatia clientes): o router orquestra router -> usecase -> repo.
# O use case e instanciado DENTRO do handler (apos a validacao do corpo e a guarda
# de DB) para preservar a ordem dos erros HTTP: 422 (corpo invalido) antes de 503
# (DB indisponivel). Plugar via Depends(get_*_uc) inverteria essa ordem.


@router.post("", status_code=201)
@limiter.limit("20/minute")
async def criar_cliente(
    request: Request,
    payload: ClienteCreate,
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL or SessionLocal is None:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as db:
        uc = CriarClienteUseCase(ClienteRepositorySQL(db))
        try:
            out = await uc.execute(
                CriarClienteInput(
                    nome=payload.nome,
                    cnpj=payload.cnpj,
                    email=payload.email,
                    telefone=payload.telefone,
                    plano=payload.plano,
                )
            )
        except RegraViolada as e:
            # "CNPJ ja cadastrado" -> 409; demais regras de negocio -> 400.
            raise HTTPException(409 if "CNPJ" in str(e) else 400, str(e))
        except ValorInvalido as e:
            raise HTTPException(400, str(e))
        except IntegrityError:
            raise HTTPException(409, "CNPJ ja cadastrado")

    cliente = out.cliente
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
        "criado_em": cliente.criado_em.isoformat() if cliente.criado_em else None,
    }


@router.get("")
@limiter.limit("30/minute")
async def listar_clientes(
    request: Request,
    apenas_ativos: bool = True,
    user: TokenPayload = Depends(current_user),
):
    if user.role not in ("admin", "service", "auditor"):
        raise HTTPException(403, "Listagem de clientes restrita a administradores")
    if not DB_DISPONIVEL or SessionLocal is None:
        raise HTTPException(503, "Banco de dados nao configurado")
    async with SessionLocal() as db:
        uc = ListarClientesUseCase(ClienteRepositorySQL(db))
        clientes = await uc.execute(ListarClientesInput(apenas_ativos=apenas_ativos))
    return [
        {"id": str(c.id), "nome": c.nome, "cnpj": c.cnpj, "email": c.email, "plano": c.plano, "ativo": c.ativo}
        for c in clientes
    ]


@router.get("/{cliente_id}")
@limiter.limit("30/minute")
async def buscar_cliente(
    request: Request,
    cliente_id: str,
    user: TokenPayload = Depends(current_user),
):
    # fix(#6): validar UUID antes de checar DB_DISPONIVEL para retornar 400
    # corretamente para IDs invalidos independente do estado do banco.
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError:
        raise HTTPException(400, "ID invalido")
    autorizar_cliente(user, cliente_id)
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
    autorizar_cliente(user, cliente_id)
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
