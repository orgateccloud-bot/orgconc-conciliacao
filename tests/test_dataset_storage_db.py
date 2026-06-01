"""Round-trip de dataset via Postgres (pulado quando não há DB acessível).

Verifica o caminho DB de api/services/storage.py: salvar grava no Postgres (não
no arquivo), carregar lê do Postgres, e a verificação de owner_sub funciona.
Limpa a linha de teste no fim. Roda com DATABASE_URL acessível + ORGCONC_RUN_DB_TESTS=1.
"""
from __future__ import annotations

import os

import pytest

from api.core import config
from api.core.config import DATA_DIR
from api.services.storage import carregar_dataset, salvar_dataset


def _db_acessivel() -> bool:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url or "[" in url:
        return False
    try:
        import psycopg2

        u = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        with psycopg2.connect(u, connect_timeout=3) as c:
            with c.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_acessivel(), reason="DATABASE_URL ausente/inacessível")


def _del_db_row(rid: str) -> None:
    import psycopg2

    url = (config._DB_URL or os.environ.get("DATABASE_URL", "")).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reconciliacao_datasets WHERE id = %s", (rid,))
        conn.commit()
    finally:
        conn.close()


def test_roundtrip_via_db():
    config.DB_DISPONIVEL = True  # ativa o caminho DB (sem propagar aos consumidores)

    rid = salvar_dataset([{"conta": "x", "qtd": 0, "transacoes": []}],
                         [{"tipo": "t"}], "rel-db", owner_sub="dbtest")
    try:
        # Foi para o DB, NÃO para o arquivo local
        assert not (DATA_DIR / f"{rid}.json").exists(), "não deveria ter caído no fallback de arquivo"

        data = carregar_dataset(rid, verify_sub="dbtest")
        assert data["relatorio"] == "rel-db"
        assert data["owner_sub"] == "dbtest"

        # owner_sub divergente → 403
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            carregar_dataset(rid, verify_sub="outro-dono")
        assert exc.value.status_code == 403
    finally:
        _del_db_row(rid)
        config.DB_DISPONIVEL = False  # restaura estado para não afetar outros testes
