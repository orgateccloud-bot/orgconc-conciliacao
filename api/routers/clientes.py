"""Router /clientes — handlers magros, delegam a use cases."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from api.core.rate_limit import limiter
from api.domain.exceptions import RegraViolada
from api.domain.value_objects import CNPJ
from api.schemas import ClienteCreate, ClienteUpdate
from api.schemas_responses import ClienteResponse
from api.services.auth import current_user
from api.usecases import (
    CriarClienteInput,
    CriarClienteUseCase,
    ListarClientesInput,
    ListarClientesUseCase,
)
from api.wiring import (
    get_cliente_repo,
    get_criar_cliente_uc,
    get_listar_clientes_uc,
)

router = APIRouter(prefix="/clientes", tags=["clientes"], dependencies=[Depends(current_user)])


def _serializar(c) -> dict:
    return {
        "id": str(c.id),
        "nome": c.nome,
        "cnpj": c.cnpj,
        "email": c.email,
        "telefone": c.telefone,
        "plano": c.plano,
        "ativo": c.ativo,
        "criado_em": c.criado_em.isoformat() if c.criado_em else None,
    }


@router.post("", status_code=201, response_model=ClienteResponse)
@limiter.limit("20/minute")
async def criar_cliente(
    request: Request,
    payload: ClienteCreate,
    uc: CriarClienteUseCase = Depends(get_criar_cliente_uc),
):
    try:
        out = await uc.execute(CriarClienteInput(
            nome=payload.nome,
            cnpj=payload.cnpj,
            email=payload.email,
            telefone=payload.telefone,
            plano=payload.plano,
        ))
    except RegraViolada as e:
        # RegraViolada -> 409 quando relacionado a unicidade, 400 caso contrario
        msg = str(e)
        if "ja cadastrado" in msg.lower():
            raise HTTPException(409, msg) from e
        raise HTTPException(400, msg) from e
    except IntegrityError:
        # Defesa em profundidade — se o repositorio levantar IntegrityError
        # (race condition entre buscar_por_cnpj e criar), traduzimos para 409.
        raise HTTPException(409, "CNPJ ja cadastrado")
    return _serializar(out.cliente)


@router.get("", response_model=list[ClienteResponse])
@limiter.limit("30/minute")
async def listar_clientes(
    request: Request,
    apenas_ativos: bool = True,
    uc: ListarClientesUseCase = Depends(get_listar_clientes_uc),
):
    clientes = await uc.execute(ListarClientesInput(apenas_ativos=apenas_ativos))
    return [_serializar(c) for c in clientes]


@router.get("/{cliente_id}", response_model=ClienteResponse)
@limiter.limit("30/minute")
async def buscar_cliente(
    request: Request,
    cliente_id: str,
    repo=Depends(get_cliente_repo),
):
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError as e:
        raise HTTPException(400, "ID invalido") from e
    cliente = await repo.buscar_por_id(cid)
    if not cliente:
        raise HTTPException(404, "Cliente nao encontrado")
    return _serializar(cliente)


@router.patch("/{cliente_id}", response_model=ClienteResponse)
@limiter.limit("20/minute")
async def atualizar_cliente(
    request: Request,
    cliente_id: str,
    payload: ClienteUpdate,
    repo=Depends(get_cliente_repo),
):
    try:
        cid = uuid.UUID(cliente_id)
    except ValueError as e:
        raise HTTPException(400, "ID invalido") from e
    campos = {k: v for k, v in payload.model_dump().items() if v is not None}
    cliente = await repo.atualizar(cid, **campos)
    if not cliente:
        raise HTTPException(404, "Cliente nao encontrado")
    return _serializar(cliente)
