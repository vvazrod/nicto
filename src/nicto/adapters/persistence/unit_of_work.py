from sqlalchemy.ext.asyncio import AsyncSession

from nicto.application.ports import UnitOfWork


class SqlaUnitOfWork(UnitOfWork):
    """Commit or rollback the transaction of a SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        """Commit the session transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the session transaction."""
        await self._session.rollback()
