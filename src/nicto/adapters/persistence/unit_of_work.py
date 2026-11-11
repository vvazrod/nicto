from sqlalchemy.ext.asyncio import AsyncSession

from nicto.application.ports import UnitOfWork


class SqlaUnitOfWork(UnitOfWork):
    """Commit the transaction of a SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        """Commit the session transaction."""
        await self._session.commit()
