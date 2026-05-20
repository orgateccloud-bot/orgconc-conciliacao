"""Conexão com PostgreSQL/Supabase via SQLAlchemy async."""
import os
from pathlib import Path as _Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

# Carrega .env SEM override — variaveis ja exportadas no shell tem precedencia
# (ex: docker-compose, systemd, CI). Antes usava override=True, que mascarava
# segredos vindos do ambiente real.
_env = _Path(__file__).resolve().parent.parent.parent / ".env"
if _env.exists():
    load_dotenv(_env, override=False)

_url_sync = os.getenv("DATABASE_URL", "").strip()
if not _url_sync:
    # Sem URL configurada -> deixa o caller (main.py) decidir o fallback.
    # main.py ja checa DB_DISPONIVEL antes de tentar conexao.
    _url_async = ""
else:
    # Heroku/Railway/Render usam postgres:// (legacy); SQLAlchemy 2.x exige postgresql://
    if _url_sync.startswith("postgres://"):
        _url_sync = _url_sync.replace("postgres://", "postgresql://", 1)
    # SQLAlchemy async exige driver asyncpg
    _url_async = _url_sync.replace("postgresql://", "postgresql+asyncpg://", 1)

_engine_kwargs = dict(
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    connect_args={"statement_cache_size": 0},  # obrigatorio com pgbouncer transaction pooler
)

# create_async_engine exige URL nao-vazia; cria engine "dummy" apenas se houver URL.
if _url_async:
    engine = create_async_engine(_url_async, **_engine_kwargs)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
else:
    engine = None
    SessionLocal = None


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency FastAPI para injetar sessão de banco."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL nao configurado. Defina no .env ou no ambiente.")
    async with SessionLocal() as session:
        yield session
