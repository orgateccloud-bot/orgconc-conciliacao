from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Response

from api.services.auth import TokenPayload, current_user
from api.services.excel import _gerar_xlsx
from api.services.render import render_html, render_pdf_html
from api.services.storage import carregar_dataset

router = APIRouter(tags=["export"])
log = logging.getLogger("orgconc.exports")


def _block_url_fetcher(url: str, **_kwargs) -> dict:
    """Bloqueia fetch de URLs externas pelo WeasyPrint (previne SSRF)."""
    log.debug("WeasyPrint bloqueou fetch externo: %s", url)
    return {"string": b"", "mime_type": "text/plain", "encoding": "utf-8"}


@router.get("/export/html/{rid}")
def export_html(rid: str, user: TokenPayload = Depends(current_user)):
    ds = carregar_dataset(rid, verify_sub=user.sub)
    html = render_html(ds["relatorio"])
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="conciliacao_{rid}.html"'},
    )


@router.get("/export/xlsx/{rid}")
def export_xlsx(rid: str, user: TokenPayload = Depends(current_user)):
    ds = carregar_dataset(rid, verify_sub=user.sub)
    blob = _gerar_xlsx(ds["extratos"], ds["anomalias"])
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="conciliacao_{rid}.xlsx"'},
    )


@router.get("/export/pdf/{rid}")
def export_pdf(rid: str, html: bool = False, user: TokenPayload = Depends(current_user)):
    ds = carregar_dataset(rid, verify_sub=user.sub)
    html_content = render_pdf_html(ds["relatorio"], ds["anomalias"], ds["extratos"], rid)
    if html:
        return Response(
            content=html_content,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="conciliacao_{rid}.html"'},
        )
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html_content, base_url=None, url_fetcher=_block_url_fetcher).write_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="conciliacao_{rid}.pdf"'},
        )
    except (ImportError, OSError, RuntimeError) as exc:
        # weasyprint requer libpango; em hosts sem ele cai pro HTML imprimivel
        log.warning("weasyprint falhou (%s): %s", type(exc).__name__, exc)
        return Response(
            content=html_content,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="conciliacao_{rid}.html"'},
        )
