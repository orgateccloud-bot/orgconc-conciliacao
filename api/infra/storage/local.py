"""LocalStorageGateway — wraps as funcoes em api/services/storage.py.

Mantida 100% retrocompat: as funcoes legadas continuam expostas; novo codigo
usa essa classe via dependency injection.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from api.services.storage import (
    carregar_dataset as _legacy_carregar,
    salvar_dataset as _legacy_salvar,
)


class LocalStorageGateway:
    """Persistencia em filesystem local com rolling window de 50 arquivos."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "LocalStorageGateway":
        from api.core.config import DATA_DIR
        return cls(DATA_DIR)

    def salvar_dataset(
        self,
        extratos: list[dict],
        anomalias: list[dict],
        relatorio: str,
        owner_sub: str | None = None,
    ) -> str:
        return _legacy_salvar(extratos, anomalias, relatorio, owner_sub=owner_sub)

    def carregar_dataset(self, rid: str, verify_sub: str | None = None) -> dict[str, Any]:
        return _legacy_carregar(rid, verify_sub=verify_sub)
