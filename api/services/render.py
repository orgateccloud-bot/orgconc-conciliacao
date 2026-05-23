"""Renderizacao de relatorios em HTML (inline e PDF)."""
from __future__ import annotations

from markdown import markdown as md_to_html

from api.core.templates import LOGO_DATA_URI, jinja_env
from api.services.sanitize import sanitize_html


def render_html(relatorio_md: str) -> str:
    from datetime import datetime
    body = md_to_html(relatorio_md, extensions=["tables", "fenced_code"])
    body = sanitize_html(body)
    return jinja_env.get_template("relatorio.html").render(
        body=body,
        agora=datetime.now().strftime("%d/%m/%Y %H:%M"),
        logo_data_uri=LOGO_DATA_URI,
    )


def render_pdf_html(relatorio_md: str, anomalias: list, extratos: list, report_id: str) -> str:
    from datetime import datetime
    body = md_to_html(relatorio_md, extensions=["tables", "fenced_code"])
    body = sanitize_html(body)
    total_tx = sum(e.get("qtd", 0) for e in extratos)
    total_cred = sum(t["valor"] for e in extratos for t in e.get("transacoes", []) if t["valor"] > 0)
    total_deb = sum(t["valor"] for e in extratos for t in e.get("transacoes", []) if t["valor"] < 0)
    n_crit = sum(1 for a in anomalias if a.get("severidade") == "critico")
    n_alerta = sum(1 for a in anomalias if a.get("severidade") == "alerta")
    n_atenc = sum(1 for a in anomalias if a.get("severidade") == "atencao")
    return jinja_env.get_template("relatorio_pdf.html").render(
        report_id=report_id,
        agora=datetime.now().strftime("%d/%m/%Y %H:%M"),
        body=body,
        anomalias=anomalias,
        n_anom=len(anomalias),
        n_crit=n_crit,
        n_alerta=n_alerta,
        n_atenc=n_atenc,
        total_tx=total_tx,
        total_cred=total_cred,
        total_deb_abs=abs(total_deb),
        n_contas=len(extratos),
        logo_data_uri=LOGO_DATA_URI,
    )
