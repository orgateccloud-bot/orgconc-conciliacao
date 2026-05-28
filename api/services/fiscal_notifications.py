"""Notificações fiscais — disparo quando fornecedor passa para CRITICO.

Sprint 4 do Plano de Integração Fiscal.

Estratégia:
- Após cada `salvar_conformidade`, verifica se houve mudança de classe
  para CRITICO. Se sim:
  1. Grava audit_event com action="fiscal.alerta_critico"
  2. Envia email (se configurado) para o responsável
  3. Persiste notificação em log estruturado

Email: usa SMTP simples via stdlib; configuração via env vars:
- FISCAL_NOTIFY_EMAIL: destinatário (vazio = desativado)
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
"""
from __future__ import annotations

import logging
import os
import re
import smtplib
from email.message import EmailMessage
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.audit import registrar_audit

log = logging.getLogger("orgconc.fiscal.notifications")

# F-06: sanitiza CR/LF para prevenir SMTP header injection
_HEADER_INJECTION_RX = re.compile(r"[\r\n\t]")


def _sanitize_header(s: str) -> str:
    """Remove CR/LF/TAB para evitar SMTP header injection (RFC 5322)."""
    if not s:
        return ""
    return _HEADER_INJECTION_RX.sub(" ", s)[:200]


def _smtp_config() -> dict[str, str]:
    return {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": os.environ.get("SMTP_PORT", "587"),
        "user": os.environ.get("SMTP_USER", ""),
        "pwd": os.environ.get("SMTP_PASS", ""),
        "from": os.environ.get("SMTP_FROM", "orgconc@orgatec.cloud"),
        "to": os.environ.get("FISCAL_NOTIFY_EMAIL", ""),
    }


def enviar_email_alerta(assunto: str, corpo: str) -> bool:
    """Envia email simples via SMTP. Retorna True se enviado.

    F-06: sanitiza headers para prevenir injection.
    """
    cfg = _smtp_config()
    if not cfg["host"] or not cfg["to"]:
        log.info("SMTP não configurado; pulando envio de email fiscal")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = _sanitize_header(assunto)
        msg["From"] = _sanitize_header(cfg["from"])
        msg["To"] = _sanitize_header(cfg["to"])
        msg.set_content(corpo)
        port = int(cfg["port"])
        if port == 465:
            with smtplib.SMTP_SSL(cfg["host"], port) as s:
                if cfg["user"]:
                    s.login(cfg["user"], cfg["pwd"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], port) as s:
                s.starttls()
                if cfg["user"]:
                    s.login(cfg["user"], cfg["pwd"])
                s.send_message(msg)
        log.info("Email fiscal enviado para %s — %s", cfg["to"], assunto)
        return True
    except Exception:
        log.exception("Falha ao enviar email fiscal")
        return False


async def notificar_classe_critica(
    db: AsyncSession,
    cliente_id: str,
    cnpj_fornecedor: str,
    razao_social: str,
    risco_anual: float,
    flags: list[str],
    classe_anterior: Optional[str] = None,
) -> None:
    """Registra evento de auditoria + envia email quando fornecedor vira CRITICO.

    Caller deve fazer commit da sessão.
    """
    payload = {
        "cliente_id": str(cliente_id),
        "cnpj_fornecedor": cnpj_fornecedor,
        "razao_social": razao_social,
        "risco_anual": round(risco_anual, 2),
        "flags": flags,
        "classe_anterior": classe_anterior,
        "classe_atual": "CRITICO",
    }
    await registrar_audit(
        db,
        action="fiscal.alerta_critico",
        resource_type="conformidade_fornecedor",
        resource_id=cnpj_fornecedor,
        payload=payload,
    )

    # F-15: assunto genérico, sem CNPJ/razão social em metadados SMTP
    assunto = "[OrgConc Fiscal] Alerta de fornecedor CRITICO"
    corpo = (
        f"Alerta de auditoria fiscal:\n\n"
        f"Cliente: {cliente_id}\n"
        f"Fornecedor: {razao_social}\n"
        f"CNPJ: {cnpj_fornecedor}\n"
        f"Risco anualizado: R$ {risco_anual:,.2f}\n"
        f"Flags: {', '.join(flags) if flags else '—'}\n"
        f"Classe anterior: {classe_anterior or 'novo'}\n\n"
        f"Acesse o painel: https://orgconc.cloud/app/conformidade-fiscal\n"
    )
    enviar_email_alerta(assunto, corpo)
