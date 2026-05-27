"""Camada de matchers — motor de conciliação automática em 6 estágios.

Integração do projeto OrgNeural2 ao OrgConc. Cada matcher resolve um estágio
da cascata (NFe, guia tributária, contrato recorrente, cadastro, etc.).
"""
from api.matchers.cascata import (  # noqa: F401
    Disposicao,
    Resultado,
    Transacao,
    classificar,
    ler_ofx,
)

__all__ = ["Disposicao", "Resultado", "Transacao", "classificar", "ler_ofx"]
