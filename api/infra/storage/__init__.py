"""Storage gateways — backend para datasets de conciliacao.

Selecao via env ORGCONC_STORAGE_BACKEND:
- local (default) -> LocalStorageGateway (DATA_DIR no FS)
- s3              -> S3StorageGateway (Supabase Storage, AWS S3, MinIO, etc.)
"""
from __future__ import annotations

import os

from api.infra.storage.gateway import StorageGateway
from api.infra.storage.local import LocalStorageGateway

_singleton: StorageGateway | None = None


def get_storage_gateway() -> StorageGateway:
    """Factory + singleton. Cache na primeira chamada."""
    global _singleton
    if _singleton is not None:
        return _singleton

    backend = os.environ.get("ORGCONC_STORAGE_BACKEND", "local").strip().lower()
    if backend == "s3":
        from api.infra.storage.s3 import S3StorageGateway
        _singleton = S3StorageGateway.from_env()
    else:
        _singleton = LocalStorageGateway.from_env()
    return _singleton


__all__ = ["StorageGateway", "LocalStorageGateway", "get_storage_gateway"]
