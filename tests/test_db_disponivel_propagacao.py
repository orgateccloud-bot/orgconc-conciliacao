"""Regressão: propagação de DB_DISPONIVEL aos routers.

Bug real (encontrado jun/2026): guias/contratos/fiscal/matchers importavam
`DB_DISPONIVEL` como snapshot (`from api.core.config import DB_DISPONIVEL`) e
checavam `if not DB_DISPONIVEL`, mas NÃO estavam em `_DB_DISPONIVEL_CONSUMERS`.
Resultado: o flag deles nunca virava True em produção (a propagação no startup
só atualiza a lista de consumers), então TODOS esses endpoints retornavam 503
mesmo com o banco no ar — 4 routers de features centrais inteiros quebrados.

Este teste varre os routers e exige que qualquer um que gateie em DB_DISPONIVEL
esteja na lista de propagação. Pega o bug original e qualquer router futuro que
esqueça de se registrar.
"""
from __future__ import annotations

import pathlib
import re

from api.core import config


def test_routers_que_gateiam_em_db_disponivel_estao_na_propagacao():
    routers_dir = pathlib.Path(config.__file__).resolve().parent.parent / "routers"
    faltando = []
    for py in sorted(routers_dir.glob("*.py")):
        if py.name == "__init__.py":
            continue
        texto = py.read_text(encoding="utf-8")
        # Gateia no snapshot importado (padrão `if not DB_DISPONIVEL`)
        if re.search(r"\bif not DB_DISPONIVEL\b", texto):
            mod = f"api.routers.{py.stem}"
            if mod not in config._DB_DISPONIVEL_CONSUMERS:
                faltando.append(mod)
    assert not faltando, (
        "Routers que checam DB_DISPONIVEL mas estão fora de _DB_DISPONIVEL_CONSUMERS "
        f"→ retornariam 503 em prod mesmo com DB no ar: {faltando}"
    )
