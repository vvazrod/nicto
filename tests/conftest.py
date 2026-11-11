from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import Connection, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from nicto.adapters.persistence.database import (
    create_engine,
    create_schema,
    create_session_factory,
)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """In-memory database engine shared by the whole test session."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")

    # Make the driver honour SAVEPOINT and outer transactions, so test rollbacks undo commits.
    @event.listens_for(engine.sync_engine, "connect")
    def _disable_driver_transactions(dbapi_connection: DBAPIConnection, _: object) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _emit_begin(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN")

    await create_schema(engine)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory shared by the whole test session."""
    return create_session_factory(engine)


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Session whose changes, including commits, are rolled back after each test."""
    async with engine.connect() as connection, connection.begin() as transaction:
        async with session_factory(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        await transaction.rollback()
