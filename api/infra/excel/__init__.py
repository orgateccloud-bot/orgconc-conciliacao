"""Gerador de XLSX para relatorios de conciliacao.

Status (item 28): em processo de quebra modular.
- styles.py     -> paleta, fontes, bordas
- (futuro) workbook_builder.py -> abas Resumo + Transacoes + Anomalias
- (atual)    api/services/excel.py mantem _gerar_xlsx como facade

Ate concluir o split, o ponto de entrada continua sendo
`from api.services.excel import _gerar_xlsx`.
"""
from api.infra.excel.styles import (
    LOGO_PATH,
    estilos_xlsx,
)

__all__ = ["LOGO_PATH", "estilos_xlsx"]
