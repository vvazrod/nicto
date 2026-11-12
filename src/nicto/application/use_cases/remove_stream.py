from nicto.application.ports import StreamRepository, UnitOfWork
from nicto.application.use_cases.publish_flexcurve import PublishFlexcurveUseCase
from nicto.domain.models import StreamID


class StreamNotFoundError(Exception):
    """Raised when the stream to remove does not exist."""


class RemoveStreamUseCase:
    """Remove a stream and its allocations from the system."""

    def __init__(
        self,
        stream_repository: StreamRepository,
        unit_of_work: UnitOfWork,
        flexcurve_publication: PublishFlexcurveUseCase | None = None,
    ) -> None:
        self._stream_repository = stream_repository
        self._unit_of_work = unit_of_work
        self._flexcurve_publication = flexcurve_publication

    async def execute(self, stream_id: StreamID) -> None:
        """Delete the stream, freeing its allocations."""
        stream = await self._stream_repository.get_stream_by_id(stream_id)
        if stream is None:
            msg = f"Stream {stream_id} was not found"
            raise StreamNotFoundError(msg)

        await self._stream_repository.delete_stream(stream_id)
        await self._unit_of_work.commit()
        if self._flexcurve_publication is not None:
            await self._flexcurve_publication.publish_ports(
                allocation.port_mac_address for allocation in stream.allocations
            )
