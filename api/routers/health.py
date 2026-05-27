from __future__ import annotations

import logging
import os

from fastapi import APIRouter
from sqlalchemy import text as sql_text

from api.core.config import DB_DISPONIVEL, SessionLocal
from api.core.templates import LOGO_DATA_URI

router = APIRouter()
log = logging.getLogger("orgconc.health")


@router.get("/")
def root():
    return {
        "service": "Conciliacao Bancaria API",
        "version": "0.5.0",
        "endpoints": [
            "/health", "/docs",
            "/conciliar/ofx", "/conciliar/csv",
            "/export/html/{report_id}", "/export/xlsx/{report_id}", "/export/pdf/{report_id}",
            "/clientes", "/conciliacoes",
            "/auth/login",
        ],
    }


@router.get("/health")
async def health():
    db_status = "nao_configurado"
    if DB_DISPONIVEL:
        try:
            async with SessionLocal() as db:
                await db.execute(sql_text("SELECT 1"))
            db_status = "ok"
        except Exception as exc:  # noqa: BLE001 — healthcheck nao deve crashar
            log.warning("healthcheck DB falhou: %s", type(exc).__name__)
            db_status = "erro"
    return {
        "status": "ok",
        "versao": "0.5.0",
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "banco_dados": db_status,
    }


@router.get("/logo-base64")
def logo_base64():
    return {"data_uri": LOGO_DATA_URI}
