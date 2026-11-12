from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from nicto.adapters.persistence.models import Base


def create_engine(database_url: str) -> AsyncEngine:
    """Create an async engine for the given database URL."""
    return create_async_engine(database_url)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a factory of isolated unit-of-work sessions bound to the engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_schema(engine: AsyncEngine) -> None:
    """Create database schema from ORM models."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def drop_schema(engine: AsyncEngine) -> None:
    """Drop database schema from ORM models."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def reset_schema(engine: AsyncEngine) -> None:
    """Drop and recreate database schema from ORM models."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


async def create_db_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """Create transactional database sessions."""
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
