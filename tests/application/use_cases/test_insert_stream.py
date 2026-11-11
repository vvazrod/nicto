import asyncio

import pytest
from pydantic_extra_types.mac_address import MacAddress

from nicto.application.use_cases.insert_stream import (
    InsertStreamUseCase,
    PortNotFoundError,
)
from nicto.config import Config
from nicto.domain.models import Link, Node, Port, Stream
from tests.application.use_cases.conftest import MockNetworkRepository, MockStreamRepository, MockUnitOfWork

SOURCE_NODE = Node(
    hostname="source",
    ports=[Port(mac_address=MacAddress("00:11:22:33:44:55"), name="eth0")],
)
DESTINATION_NODE = Node(
    hostname="destination",
    ports=[Port(mac_address=MacAddress("00:11:22:33:44:56"), name="eth0")],
)
STREAM = Stream(
    src_mac_address=SOURCE_NODE.ports[0].mac_address,
    dst_mac_address=DESTINATION_NODE.ports[0].mac_address,
    max_frame_size=1500,
    max_interval_frames=1,
    interval=1_000,
    max_latency=10_000,
)
CONFIG = Config(hyperperiod=100_000, tick_granularity=1_000)
LINK = Link(
    port_a_mac_address=SOURCE_NODE.ports[0].mac_address,
    port_b_mac_address=DESTINATION_NODE.ports[0].mac_address,
    speed=1_000,
    propagation_delay=0,
)


def test_execute_retrieves_stream_endpoints_before_persisting(
    network_repository: MockNetworkRepository,
    stream_repository: MockStreamRepository,
    unit_of_work: MockUnitOfWork,
) -> None:
    """Test stream insertion looks up both endpoint ports."""
    network_repository.nodes = [SOURCE_NODE, DESTINATION_NODE]
    use_case = InsertStreamUseCase(network_repository, stream_repository, unit_of_work, CONFIG)

    result = asyncio.run(use_case.execute(STREAM))

    assert network_repository.requested_mac_addresses == [
        str(STREAM.src_mac_address),
        str(STREAM.dst_mac_address),
    ]
    assert stream_repository.streams == [STREAM]
    assert unit_of_work.commits == 1
    assert isinstance(result, Stream)


def test_execute_raises_when_an_endpoint_port_is_missing(
    network_repository: MockNetworkRepository,
    stream_repository: MockStreamRepository,
    unit_of_work: MockUnitOfWork,
) -> None:
    """Test a stream with a missing endpoint port is not persisted."""
    network_repository.nodes = [SOURCE_NODE, DESTINATION_NODE]
    use_case = InsertStreamUseCase(network_repository, stream_repository, unit_of_work, CONFIG)
    stream = STREAM.model_copy(update={"dst_mac_address": "00:11:22:33:44:57"})

    with pytest.raises(PortNotFoundError, match="source or destination port"):
        asyncio.run(use_case.execute(stream))

    assert stream_repository.streams == []
    assert unit_of_work.commits == 0
