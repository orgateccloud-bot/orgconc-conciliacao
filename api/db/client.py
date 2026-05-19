"""Conexão com PostgreSQL/Supabase via SQLAlchemy async."""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

from pathlib import Path as _Path
_env = _Path(__file__).resolve().parent.parent.parent / ".env"
if _env.exists():
    load_dotenv(_env, override=True)

_url_sync = os.getenv("DATABASE_URL", "")
# SQLAlchemy async exige driver asyncpg; converte prefixo se necessário
_url_async = _url_sync.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(_url_async, pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency FastAPI para injetar sessão de banco."""
    async with SessionLocal() as session:
        yield session
