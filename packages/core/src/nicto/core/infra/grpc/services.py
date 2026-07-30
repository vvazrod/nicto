from typing import override

from nicto.apis import AddStreamRequest, AddStreamResponse, AddStreamResponseStatus, SchedulingServiceBase
from nicto.core.config import Config
from nicto.core.entities import Stream
from nicto.core.ports.persistence import NetworkRepository, StreamRepository
from nicto.core.use_cases.insert_stream import (
    InsertStreamUseCase,
    PortNotConnectedError,
    PortNotFoundError,
    StreamUnfeasibleError,
)
from pydantic_extra_types.mac_address import MacAddress


class SchedulingService(SchedulingServiceBase):
    """Handle scheduling protobuf requests."""

    def __init__(
        self,
        network_repository: NetworkRepository,
        stream_repository: StreamRepository,
        config: Config,
    ) -> None:
        """Initialize the service with its stream persistence boundary."""
        self._network_repository = network_repository
        self._stream_repository = stream_repository
        self._config = config

    @override
    async def add_stream(self, message: AddStreamRequest) -> AddStreamResponse:
        """Persist a requested stream and return its scheduling status."""
        stream = Stream(
            src_mac_address=MacAddress(message.src_mac_address),
            dst_mac_address=MacAddress(message.dst_mac_address),
            max_frame_size=message.max_frame_size,
            max_interval_frames=message.max_interval_frames,
            interval=message.interval,
            max_latency=message.max_latency,
        )

        use_case = InsertStreamUseCase(self._network_repository, self._stream_repository, self._config)
        try:
            await use_case.execute(stream)
        except PortNotFoundError:
            return AddStreamResponse(status=AddStreamResponseStatus.PORT_NOT_FOUND)
        except (PortNotConnectedError, StreamUnfeasibleError):
            return AddStreamResponse(status=AddStreamResponseStatus.UNFEASIBLE)

        return AddStreamResponse(status=AddStreamResponseStatus.SUCCESS)
