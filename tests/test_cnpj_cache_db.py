"""Round-trip do cache de CNPJ via Postgres (pulado quando não há DB acessível).

Verifica que _salvar_cache grava em cnpj_cache e _carregar_cache lê de volta.
Limpa a linha de teste. Roda com DATABASE_URL acessível.
"""
from __future__ import annotations

import os

import pytest

from api.core import config
from api.matchers import cnpj_enricher


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


def _del(cnpj: str) -> None:
    import psycopg2

    url = (config._DB_URL or os.environ.get("DATABASE_URL", "")).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cnpj_cache WHERE cnpj = %s", (cnpj,))
        conn.commit()
    finally:
        conn.close()


def test_cnpj_cache_roundtrip_via_db():
    config.DB_DISPONIVEL = True  # ativa o caminho DB (sem propagar)
    cnpj = "99888777000166"
    try:
        cnpj_enricher._salvar_cache({cnpj: {"cnpj": cnpj, "situacao": "BAIXADA", "porte": "DEMAIS"}})
        cache = cnpj_enricher._carregar_cache()
        assert cache.get(cnpj, {}).get("situacao") == "BAIXADA"
    finally:
        _del(cnpj)
        config.DB_DISPONIVEL = False
