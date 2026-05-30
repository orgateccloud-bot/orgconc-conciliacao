"""Interface (Protocol) do StorageGateway."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StorageGateway(Protocol):
    """Persistencia de datasets de conciliacao (relatorio + anomalias + extratos).

    Implementacoes:
    - LocalStorageGateway (FS local com rolling window)
    - S3StorageGateway (Supabase Storage / AWS S3 / MinIO)
    """

    def salvar_dataset(
        self,
        extratos: list[dict],
        anomalias: list[dict],
        relatorio: str,
        owner_sub: str | None = None,
    ) -> str:
        """Salva e retorna o `report_id` (12 hex chars)."""
        ...

    def carregar_dataset(self, rid: str, verify_sub: str | None = None) -> dict[str, Any]:
        """Carrega por rid. Verifica owner se verify_sub fornecido."""
        ...
