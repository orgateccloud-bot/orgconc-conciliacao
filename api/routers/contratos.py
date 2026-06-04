"""CRUD de contratos recorrentes (aluguel, seguro, leasing, consórcio)."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.db.models import Contrato
from api.services.audit import gravar_audit_independente
from api.services.auth import TokenPayload, autorizar_cliente, current_user

router = APIRouter(prefix="/contratos", tags=["contratos"], dependencies=[Depends(current_user)])

_PERIODICIDADES = {"mensal", "bimestral", "trimestral", "semestral", "anual"}


class ContratoCreate(BaseModel):
    cliente_id: uuid.UUID
    descricao: str = Field(min_length=2, max_length=200)
    valor: Decimal = Field(gt=0)
    periodicidade: Optional[str] = "mensal"
    padrao_memo: Optional[str] = None
    conta_contabil: Optional[str] = None

    def model_post_init(self, __context) -> None:
        if self.periodicidade and self.periodicidade.lower() not in _PERIODICIDADES:
            raise ValueError(f"Periodicidade inválida: {self.periodicidade}")
        if self.periodicidade:
            self.periodicidade = self.periodicidade.lower()


class ContratoUpdate(BaseModel):
    descricao: Optional[str] = None
    valor: Optional[Decimal] = None
    periodicidade: Optional[str] = None
    padrao_memo: Optional[str] = None
    conta_contabil: Optional[str] = None
    ativo: Optional[bool] = None


def _serial(c: Contrato) -> dict:
    return {
        "id": str(c.id),
        "cliente_id": str(c.cliente_id),
        "descricao": c.descricao,
        "valor": float(c.valor),
        "periodicidade": c.periodicidade,
        "padrao_memo": c.padrao_memo,
        "conta_contabil": c.conta_contabil,
        "ativo": c.ativo,
        "criado_em": c.criado_em.isoformat(),
    }


@router.post("", status_code=201)
@limiter.limit("20/minute")
async def criar_contrato(
    request: Request,
    payload: ContratoCreate,
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    autorizar_cliente(user, str(payload.cliente_id))
    async with SessionLocal() as db:
        c = Contrato(
            cliente_id=payload.cliente_id,
            descricao=payload.descricao,
            valor=payload.valor,
            periodicidade=payload.periodicidade,
            padrao_memo=payload.padrao_memo,
            conta_contabil=payload.conta_contabil,
        )
        db.add(c)
        await db.commit()
        await db.refresh(c)

    await gravar_audit_independente(
        action="contrato.criar",
        resource_type="contrato",
        resource_id=str(c.id),
        payload={"descricao": c.descricao, "valor": float(c.valor)},
        actor=user,
    )
    return _serial(c)


@router.get("")
@limiter.limit("30/minute")
async def listar_contratos(
    request: Request,
    cliente_id: Optional[str] = None,
    apenas_ativos: bool = True,
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    # Isolamento por tenant: usuário não-privilegiado só vê o próprio cliente.
    if user.role not in ("admin", "service", "auditor", "anonymous"):
        if not cliente_id:
            cliente_id = user.cliente_id
        elif user.cliente_id and cliente_id != user.cliente_id:
            raise HTTPException(403, "Acesso negado a este cliente")
    async with SessionLocal() as db:
        stmt = select(Contrato)
        if cliente_id:
            try:
                cid = uuid.UUID(cliente_id)
            except ValueError:
                raise HTTPException(400, "cliente_id inválido")
            stmt = stmt.where(Contrato.cliente_id == cid)
        if apenas_ativos:
            stmt = stmt.where(Contrato.ativo.is_(True))
        stmt = stmt.order_by(Contrato.criado_em.desc()).limit(200)
        contratos = (await db.execute(stmt)).scalars().all()
    return [_serial(c) for c in contratos]


@router.patch("/{contrato_id}")
@limiter.limit("20/minute")
async def atualizar_contrato(
    request: Request,
    contrato_id: str,
    payload: ContratoUpdate,
    user: TokenPayload = Depends(current_user),
):
    try:
        cid = uuid.UUID(contrato_id)
    except ValueError:
        raise HTTPException(400, "ID inválido")
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")

    campos = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "periodicidade" in campos:
        campos["periodicidade"] = campos["periodicidade"].lower()
        if campos["periodicidade"] not in _PERIODICIDADES:
            raise HTTPException(400, f"Periodicidade inválida: {campos['periodicidade']}")
    if not campos:
        raise HTTPException(400, "Nada para atualizar")

    async with SessionLocal() as db:
        contrato = (
            await db.execute(select(Contrato).where(Contrato.id == cid))
        ).scalar_one_or_none()
        if not contrato:
            raise HTTPException(404, "Contrato não encontrado")
        autorizar_cliente(user, str(contrato.cliente_id))
        await db.execute(update(Contrato).where(Contrato.id == cid).values(**campos))
        await db.commit()
        await db.refresh(contrato)

    await gravar_audit_independente(
        action="contrato.atualizar",
        resource_type="contrato",
        resource_id=str(contrato.id),
        payload={"campos": list(campos.keys())},
        actor=user,
    )
    return _serial(contrato)
