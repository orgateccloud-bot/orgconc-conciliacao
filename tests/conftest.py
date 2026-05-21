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
