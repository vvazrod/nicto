from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from nicto.core.infra.db.models import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class Database:
    """Owns the in-memory SQLite engine and sessions used by the application."""

    def __init__(self, url: str = DATABASE_URL) -> None:
        self._engine = create_async_engine(url)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        """Create database schema from ORM models."""
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield an isolated unit-of-work session."""
        async with self._session_factory() as session:
            yield session

    async def dispose(self) -> None:
        """Release database resources when the server stops."""
        await self._engine.dispose()
