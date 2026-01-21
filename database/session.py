from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from config import settings
from database.models import Base

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL;"))
        await conn.execute(text("PRAGMA synchronous=NORMAL;"))
        await conn.execute(text("PRAGMA cache_size=-64000;")) # 64MB cache
        await conn.run_sync(Base.metadata.create_all)
        
        # Simple migration for last_active
        try:
            # Check if column exists
            result = await conn.execute(text("PRAGMA table_info(users)"))
            columns = [row.name for row in result.fetchall()]
            if "last_active" not in columns:
                await conn.execute(text("ALTER TABLE users ADD COLUMN last_active TIMESTAMP"))
        except Exception as e:
            print(f"Migration error: {e}")
