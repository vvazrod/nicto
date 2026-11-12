from nicto.application.ports import StreamRepository, UnitOfWork
from nicto.domain.models import StreamID


class StreamNotFoundError(Exception):
    """Raised when the stream to remove does not exist."""


class RemoveStreamUseCase:
    """Remove a stream and its allocations from the system."""

    def __init__(self, stream_repository: StreamRepository, unit_of_work: UnitOfWork) -> None:
        self._stream_repository = stream_repository
        self._unit_of_work = unit_of_work

    async def execute(self, stream_id: StreamID) -> None:
        """Delete the stream, freeing its allocations."""
        if await self._stream_repository.get_stream_by_id(stream_id) is None:
            msg = f"Stream {stream_id} was not found"
            raise StreamNotFoundError(msg)

        await self._stream_repository.delete_stream(stream_id)
        await self._unit_of_work.commit()
