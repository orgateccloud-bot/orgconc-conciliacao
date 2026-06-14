"""CRUD de guias tributárias (DARF, DAS, GPS, GNRE...)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.rate_limit import limiter
from api.db.models import GuiaTributo
from api.services.audit import gravar_audit_independente
from api.services.auth import TokenPayload, autorizar_cliente, current_user, escopo_cliente_listagem

router = APIRouter(prefix="/guias", tags=["guias"], dependencies=[Depends(current_user)])

_TIPOS_VALIDOS = {"DARF", "DAS", "GPS", "GNRE", "DAE", "DARJ"}


class GuiaCreate(BaseModel):
    cliente_id: uuid.UUID
    tipo: str = Field(min_length=2, max_length=20)
    valor: Decimal = Field(gt=0)
    codigo_receita: Optional[str] = None
    competencia: Optional[str] = Field(default=None, max_length=20)
    data_vencimento: Optional[date] = None
    conta_contabil: Optional[str] = None

    def model_post_init(self, __context) -> None:
        if self.tipo.upper() not in _TIPOS_VALIDOS:
            raise ValueError(f"Tipo inválido: {self.tipo}. Use {sorted(_TIPOS_VALIDOS)}")
        self.tipo = self.tipo.upper()


class GuiaUpdate(BaseModel):
    tipo: Optional[str] = None
    valor: Optional[Decimal] = None
    codigo_receita: Optional[str] = None
    competencia: Optional[str] = None
    data_vencimento: Optional[date] = None
    conta_contabil: Optional[str] = None
    ativo: Optional[bool] = None


def _serial(g: GuiaTributo) -> dict:
    return {
        "id": str(g.id),
        "cliente_id": str(g.cliente_id),
        "tipo": g.tipo,
        "codigo_receita": g.codigo_receita,
        "valor": float(g.valor),
        "competencia": g.competencia,
        "data_vencimento": g.data_vencimento.isoformat() if g.data_vencimento else None,
        "conta_contabil": g.conta_contabil,
        "ativo": g.ativo,
        "criado_em": g.criado_em.isoformat(),
    }


@router.post("", status_code=201)
@limiter.limit("20/minute")
async def criar_guia(
    request: Request,
    payload: GuiaCreate,
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    autorizar_cliente(user, str(payload.cliente_id))
    async with SessionLocal() as db:
        guia = GuiaTributo(
            cliente_id=payload.cliente_id,
            tipo=payload.tipo,
            valor=payload.valor,
            codigo_receita=payload.codigo_receita,
            competencia=payload.competencia,
            data_vencimento=payload.data_vencimento,
            conta_contabil=payload.conta_contabil,
        )
        db.add(guia)
        await db.commit()
        await db.refresh(guia)

    await gravar_audit_independente(
        action="guia.criar",
        resource_type="guia_tributo",
        resource_id=str(guia.id),
        payload={"tipo": guia.tipo, "valor": float(guia.valor)},
        actor=user,
    )
    return _serial(guia)


@router.get("")
@limiter.limit("30/minute")
async def listar_guias(
    request: Request,
    cliente_id: Optional[str] = None,
    apenas_ativos: bool = True,
    user: TokenPayload = Depends(current_user),
):
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")
    # Escopo de tenant centralizado (nega anonymous em prod; user → próprio cliente)
    cliente_id = escopo_cliente_listagem(user, cliente_id)
    async with SessionLocal() as db:
        stmt = select(GuiaTributo)
        if cliente_id:
            try:
                cid = uuid.UUID(cliente_id)
            except ValueError:
                raise HTTPException(400, "cliente_id inválido")
            stmt = stmt.where(GuiaTributo.cliente_id == cid)
        if apenas_ativos:
            stmt = stmt.where(GuiaTributo.ativo.is_(True))
        stmt = stmt.order_by(GuiaTributo.criado_em.desc()).limit(200)
        guias = (await db.execute(stmt)).scalars().all()
    return [_serial(g) for g in guias]


@router.patch("/{guia_id}")
@limiter.limit("20/minute")
async def atualizar_guia(
    request: Request,
    guia_id: str,
    payload: GuiaUpdate,
    user: TokenPayload = Depends(current_user),
):
    try:
        gid = uuid.UUID(guia_id)
    except ValueError:
        raise HTTPException(400, "ID inválido")
    if not DB_DISPONIVEL:
        raise HTTPException(503, "Banco de dados nao configurado")

    campos = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "tipo" in campos:
        campos["tipo"] = campos["tipo"].upper()
        if campos["tipo"] not in _TIPOS_VALIDOS:
            raise HTTPException(400, f"Tipo inválido. Use {sorted(_TIPOS_VALIDOS)}")
    if not campos:
        raise HTTPException(400, "Nada para atualizar")

    async with SessionLocal() as db:
        guia = (
            await db.execute(select(GuiaTributo).where(GuiaTributo.id == gid))
        ).scalar_one_or_none()
        if not guia:
            raise HTTPException(404, "Guia não encontrada")
        autorizar_cliente(user, str(guia.cliente_id))
        await db.execute(update(GuiaTributo).where(GuiaTributo.id == gid).values(**campos))
        await db.commit()
        await db.refresh(guia)

    await gravar_audit_independente(
        action="guia.atualizar",
        resource_type="guia_tributo",
        resource_id=str(guia.id),
        payload={"campos": list(campos.keys())},
        actor=user,
    )
    return _serial(guia)
