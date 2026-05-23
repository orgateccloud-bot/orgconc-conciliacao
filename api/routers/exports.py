from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from api.services.auth import current_user
from api.services.excel import _gerar_xlsx
from api.services.persistencia import carregar_dataset, render_html, render_pdf_html

router = APIRouter(tags=["export"], dependencies=[Depends(current_user)])


@router.get("/export/html/{rid}")
def export_html(rid: str):
    ds = carregar_dataset(rid)
    html = render_html(ds["relatorio"])
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="conciliacao_{rid}.html"'},
    )


@router.get("/export/xlsx/{rid}")
def export_xlsx(rid: str):
    ds = carregar_dataset(rid)
    blob = _gerar_xlsx(ds["extratos"], ds["anomalias"])
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="conciliacao_{rid}.xlsx"'},
    )


@router.get("/export/pdf/{rid}")
def export_pdf(rid: str, html: bool = False):
    import logging
    ds = carregar_dataset(rid)
    html_content = render_pdf_html(ds["relatorio"], ds["anomalias"], ds["extratos"], rid)
    if html:
        return Response(
            content=html_content,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="conciliacao_{rid}.html"'},
        )
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html_content, base_url=None).write_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="conciliacao_{rid}.pdf"'},
        )
    except Exception as exc:
        logging.getLogger("orgconc").warning("weasyprint falhou: %s", exc)
        return Response(
            content=html_content,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="conciliacao_{rid}.html"'},
        )
