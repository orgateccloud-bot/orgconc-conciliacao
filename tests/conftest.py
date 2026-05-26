"""Configuração pytest: substitui engine por NullPool nos testes para evitar
conflito de event loop entre requisições do TestClient."""

import os
import sys
from pathlib import Path

# Garante que o pacote raiz está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Carrega .env antes de qualquer import do projeto
from dotenv import load_dotenv

_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    load_dotenv(_env, override=True)

# Zera backoff de retry da Anthropic em testes (evita 14s de sleep em testes que
# disparam APIStatusError 5xx). Setado antes de qualquer import do projeto.
os.environ.setdefault("ORGCONC_LLM_RETRY_BASE_DELAY", "0")


def _db_url_configurada() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url or "[" in url:
        return ""
    return url


def _db_acessivel(timeout_s: int = 3) -> bool:
    """True apenas se DATABASE_URL existir e aceitar conexão."""
    url = _db_url_configurada().replace("postgresql+asyncpg://", "postgresql://", 1)
    if not url:
        return False
    try:
        import psycopg2

        with psycopg2.connect(url, connect_timeout=timeout_s) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


def _forcar_db_tests() -> bool:
    return os.environ.get("ORGCONC_RUN_DB_TESTS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


# Evita falhas quando .env tem placeholder Supabase sem Postgres real.
# config.py respeita _ORGCONC_TESTS_DB_SKIP mesmo após reload do .env.
if _db_url_configurada() and not _forcar_db_tests() and not _db_acessivel():
    os.environ["_ORGCONC_TESTS_DB_SKIP"] = "1"
    os.environ.pop("DATABASE_URL", None)


def pytest_configure(config):
    """Troca o engine SQLAlchemy por NullPool assim que o módulo db é importado."""
    _patch_engine_nullpool()


def _patch_engine_nullpool():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url or "[" in db_url:
        return

    url_async = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    from sqlalchemy.pool import NullPool
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    import api.db.client as _client

    _client.engine = create_async_engine(
        url_async,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )
    _client.SessionLocal = async_sessionmaker(_client.engine, class_=AsyncSession, expire_on_commit=False)
