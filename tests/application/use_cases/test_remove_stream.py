import asyncio

import pytest
from pydantic_extra_types.mac_address import MacAddress

from nicto.application.use_cases.remove_stream import RemoveStreamUseCase, StreamNotFoundError
from nicto.domain.models import Stream, StreamID
from tests.application.use_cases.conftest import MockStreamRepository, MockUnitOfWork

MAC = MacAddress("00:11:22:33:44:55")
STREAM = Stream(
    id=StreamID(mac_address=MAC, unique_id=1),
    src_mac_address=MAC,
    dst_mac_address=MacAddress("00:11:22:33:44:56"),
    max_frame_size=100,
    max_interval_frames=1,
    interval=1_000,
    max_latency=10_000,
)


def test_execute_removes_stream_and_commits(
    stream_repository: MockStreamRepository,
    unit_of_work: MockUnitOfWork,
) -> None:
    """Test an existing stream is deleted and the change committed."""
    stream_repository.streams.append(STREAM)

    asyncio.run(RemoveStreamUseCase(stream_repository, unit_of_work).execute(STREAM.id))

    assert stream_repository.streams == []
    assert unit_of_work.commits == 1


def test_execute_raises_when_stream_is_missing(
    stream_repository: MockStreamRepository,
    unit_of_work: MockUnitOfWork,
) -> None:
    """Test removing an unknown stream fails without committing."""
    with pytest.raises(StreamNotFoundError):
        asyncio.run(RemoveStreamUseCase(stream_repository, unit_of_work).execute(STREAM.id))

    assert unit_of_work.commits == 0
