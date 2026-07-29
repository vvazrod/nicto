from typing import override

from nicto.apis import AddStreamRequest, AddStreamResponse, AddStreamResponseStatus, SchedulingServiceBase
from nicto.core.entities import Stream
from nicto.core.ports.persistence import StreamRepository
from nicto.core.use_cases.insert_stream import InsertStreamUseCase


class SchedulingGrpcHandler(SchedulingServiceBase):
    """Handle scheduling protobuf requests."""

    def __init__(self, repository: StreamRepository) -> None:
        """Initialize the service with its stream persistence boundary."""
        self._repository = repository

    @override
    async def add_stream(self, message: "AddStreamRequest") -> "AddStreamResponse":
        """Persist a requested stream and return its scheduling status."""
        stream = Stream(
            src_mac=message.src_mac,
            dst_mac=message.dst_mac,
            vlan_id=message.vlan_id,
            priority=message.priority,
            max_frame_size=message.max_frame_size,
            max_num_frames=message.max_num_frames,
            measurement_interval=message.measurement_interval,
            deadline=message.deadline,
        )

        use_case = InsertStreamUseCase(self._repository)
        result = use_case.execute(stream)

        del result

        return AddStreamResponse(status=AddStreamResponseStatus.SUCCESS)
