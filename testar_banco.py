"""Testa conexão com Supabase e cria as tabelas via SQLAlchemy."""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from api.db.client import engine, Base
from api.db import models  # garante que os modelos são registrados


async def main():
    print("Testando conexão com Supabase...")
    async with engine.begin() as conn:
        # cria tabelas que ainda não existem (não apaga as existentes)
        await conn.run_sync(Base.metadata.create_all)
    print("Tabelas criadas/verificadas com sucesso!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
